from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session
from adapters.mongo_adapter import search_recipes as mongo_search_recipes
from adapters.sql_adapter import get_user_allergy_ingredient_ids
from services.recipe_service import get_recipe_by_id
from adapters.graph_adapter import check_conflicts as neo_check_conflicts, choose_substitute_for


logger = logging.getLogger("smartmeal.planner")


@dataclass
class PlanRequest:
    user_id: uuid.UUID
    week_start: date
    days: int = 7
    use_substitutions: bool = False


class PlannerService:
    """
    Planner (MVP):
    - pulls pantry and user allergens from Postgres
    - gets candidates from Mongo
    - checks conflicts via Neo4j and applies substitutions if necessary
    - scores for pantry matches + easy cuisine diversification
    - writes meal_plan and meal_entry
    - returns plan_id
    """

    def __init__(self, db: Session):
        self.db: Session = db

    def _user_exists(self, user_id: uuid.UUID) -> bool:
        sql = "SELECT 1 FROM app_user WHERE user_id = :uid LIMIT 1"
        row = self.db.execute(text(sql), {"uid": str(user_id)}).first()
        return bool(row)

    def _load_pantry(self, user_id: uuid.UUID) -> List[Dict[str, Any]]:
        sql = """
        SELECT ingredient_id::text AS ingredient_id, quantity, unit, best_before
        FROM pantry_item
        WHERE user_id = :uid
        """
        rows = self.db.execute(text(sql), {"uid": str(user_id)}).mappings().all()
        return [dict(r) for r in rows]

    def _insert_meal_plan(self, user_id: uuid.UUID, starts_on: date, ends_on: date) -> uuid.UUID:
        """
        Table: meal_plan(plan_id uuid pk, user_id uuid, starts_on date, ends_on date, title text null, created_at timestamptz default now())
        """
        plan_id = uuid.uuid4()
        sql = """
        INSERT INTO meal_plan (plan_id, user_id, starts_on, ends_on)
        VALUES (:pid, :uid, :start_on, :end_on)
        """
        self.db.execute(
            text(sql),
            {"pid": str(plan_id), "uid": str(user_id), "start_on": starts_on, "end_on": ends_on},
        )
        return plan_id

    def _insert_meal_entry(self, plan_id: uuid.UUID, day_idx: int, recipe_id: str, servings: int = 2) -> None:
        """
        Table: meal_entry(meal_entry_id uuid pk default gen_random_uuid(),
                            plan_id uuid fk -> meal_plan.plan_id,
                            recipe_id text, day_index int, servings int, created_at timestamptz default now())
        """
        sql = """
        INSERT INTO meal_entry (plan_id, recipe_id, day_index, servings)
        VALUES (:pid, :rid, :dix, :srv)
        """
        self.db.execute(
            text(sql),
            {"pid": str(plan_id), "rid": str(recipe_id), "dix": day_idx, "srv": servings},
        )

    # ---------- candidate fetch ----------

    def _fetch_candidates(self, pantry: List[Dict[str, Any]]) -> List[Dict[str, Any]]:

        candidates: List[Dict[str, Any]] = []
        try:
            q_list = ["quick", "baked", "salad", "soup", "chicken", "beef", "pasta", "main-dish", "vegetarian", "dessert"]
            for q in q_list:
                part = mongo_search_recipes(query=q, tags=None, exclude_ingredient_ids=None, limit=20)
                candidates.extend(part or [])
        except Exception as e:
            logger.warning("Mongo candidate fetch failed: %s", e)
            return []

        seen: set[str] = set()
        uniq: List[Dict[str, Any]] = []
        for c in candidates:
            rid = c.get("_id") or c.get("id")
            rid = str(rid) if rid is not None else None
            if rid and rid not in seen:
                seen.add(rid)
                uniq.append({**c, "_id": rid})
        logger.info("mongo candidates uniq=%d", len(uniq))
        return uniq

    # ---------- conflict resolution with Neo4j ----------

    def _resolve_conflicts_with_neo4j(
            self,
            ingredient_ids: list[str],
            user_id: uuid.UUID,
            allergen_ids: set[str],
            allow_subs: bool,
            max_subs_per_recipe: int = 3,
    ) -> tuple[bool, list[str]]:
        if not ingredient_ids:
            return True, []

        conflicts = neo_check_conflicts(ingredient_ids, str(user_id))
        if not conflicts:
            return True, ingredient_ids

        if not allow_subs:
            logger.info("Recipe has conflicts but substitutions disabled: %s", list(conflicts.keys()))
            return False, ingredient_ids

        effective = list(ingredient_ids)
        subs_made = 0
        disallowed = set(allergen_ids)

        for bad_id in list(conflicts.keys()):
            sub = choose_substitute_for(bad_id, disallowed_ids=disallowed, limit=5)
            if not sub:
                logger.info("No valid substitute found for conflicting ingredient %s", bad_id)
                return False, ingredient_ids

            for idx, val in enumerate(effective):
                if val == bad_id:
                    logger.info("Substituting %s -> %s", bad_id, sub)
                    effective[idx] = sub
                    subs_made += 1
                    break

            if subs_made >= max_subs_per_recipe:
                break

        logger.info("Applied %d substitutions successfully", subs_made)
        return True, effective

    # ---------- scoring ----------

    def _score_recipe(
            self,
            recipe: Dict[str, Any],
            pantry_ids: set[str],
            allergen_ids: set[str],
            used_cuisines: set[str],
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Score:
        - ingredient overlap with pantry items
        - bonus for a new kitchen
        - strict allergen exclusion
        """
        ingredients = recipe.get("ingredients", []) or []
        r_ing_ids = {str(ing.get("ingredient_id")) for ing in ingredients if ing.get("ingredient_id")}

        if r_ing_ids & allergen_ids:
            return (-1.0, {"reason": "allergy-conflict"})

        overlap = len(r_ing_ids & pantry_ids)
        total = len(r_ing_ids) or 1
        pantry_score = overlap / total  # [0..1]

        cuisine = (recipe.get("cuisine") or recipe.get("cuisine_id") or "").strip()
        diversity_bonus = 0.15 if (cuisine and cuisine not in used_cuisines) else 0.0

        return (pantry_score + diversity_bonus, {"overlap": overlap, "total": total, "cuisine": cuisine})

    # ---------- main ----------

    def generate_plan(self, req: PlanRequest) -> uuid.UUID:
        if not self._user_exists(req.user_id):
            raise ValueError(f"User {req.user_id} not found")

        ws = req.week_start - timedelta(days=req.week_start.weekday())
        we = ws + timedelta(days=max(req.days, 1) - 1)

        pantry = self._load_pantry(req.user_id)
        pantry_ids: set[str] = {str(p["ingredient_id"]) for p in pantry if p.get("ingredient_id")}
        allergen_ids: set[str] = set(map(str, get_user_allergy_ingredient_ids(str(req.user_id)) or []))

        logger.info("User %s: pantry=%d items, allergens=%d", req.user_id, len(pantry_ids), len(allergen_ids))

        candidates = self._fetch_candidates(pantry)
        if not candidates:
            raise ValueError("No recipe candidates found in MongoDB")

        scored: List[Tuple[float, str, Dict[str, Any]]] = []

        for c in candidates:
            rid = str(c.get("_id") or c.get("id") or "")
            if not rid:
                continue

            ingredients = c.get("ingredients", []) or []
            raw_ing_ids = [str(i.get("ingredient_id")) for i in ingredients if i.get("ingredient_id")]
            cuisine = (c.get("cuisine") or c.get("cuisine_id") or "").strip()

            ok, eff_ing_ids = self._resolve_conflicts_with_neo4j(
                ingredient_ids=raw_ing_ids,
                user_id=req.user_id,
                allergen_ids=allergen_ids,
                allow_subs=req.use_substitutions,
            )

            if not ok:
                logger.debug("Recipe %s has unresolvable conflicts, skipping", rid)
                continue

            tmp_recipe = {
                "ingredients": [{"ingredient_id": iid} for iid in eff_ing_ids],
                "cuisine": cuisine,
                "cuisine_id": c.get("cuisine_id") or "",
            }

            score, meta = self._score_recipe(tmp_recipe, pantry_ids, allergen_ids, set())
            if score >= 0:
                scored.append((score, rid, meta))

        logger.info("Scored %d recipes after conflict resolution", len(scored))

        if not scored:
            raise ValueError("No suitable recipes found after conflict checking")

        scored.sort(key=lambda t: t[0], reverse=True)

        used_cuisines: set[str] = set()
        picks: List[str] = []

        for score, rid, meta in scored:
            rdoc = get_recipe_by_id(rid)
            if not rdoc:
                logger.debug("Recipe %s not found in full fetch, skipping", rid)
                continue

            cuisine = (rdoc.get("cuisine") or rdoc.get("cuisine_id") or "").strip()

            # The first 3 days - we try different cuisines
            if cuisine and cuisine in used_cuisines and len(picks) < 3:
                continue

            picks.append(rid)
            if cuisine:
                used_cuisines.add(cuisine)

            if len(picks) >= req.days:
                break

        # Fallback: If you still don't have enough recipes, take them without taking into account the variety
        if len(picks) < req.days:
            logger.warning("Only %d diverse recipes found, filling with remaining", len(picks))
            for _, rid, _ in scored:
                if rid not in picks:
                    picks.append(rid)
                    if len(picks) >= req.days:
                        break

        if not picks:
            raise ValueError("Could not select any recipes for the plan")

        logger.info("Selected %d recipes for plan (requested: %d)", len(picks), req.days)

        plan_id = self._insert_meal_plan(req.user_id, ws, we)
        for i, rid in enumerate(picks):
            self._insert_meal_entry(plan_id, i, rid, servings=2)

        self.db.commit()

        logger.info("Generated plan %s for user %s with %d entries", plan_id, req.user_id, len(picks))
        return plan_id

    # ---------- queries for API ----------

    def list_user_plans(self, user_id: uuid.UUID):
        sql = """
        SELECT
          mp.plan_id                       AS plan_id,
          mp.user_id                       AS user_id,
          mp.starts_on                     AS week_start,
          COUNT(me.meal_entry_id)::int     AS days
        FROM meal_plan mp
        LEFT JOIN meal_entry me ON me.plan_id = mp.plan_id
        WHERE mp.user_id = :uid
        GROUP BY mp.plan_id, mp.user_id, mp.starts_on
        ORDER BY mp.starts_on DESC
        """
        rows = self.db.execute(text(sql), {"uid": str(user_id)}).mappings().all()
        return [dict(r) for r in rows]

    def get_plan_entries(self, plan_id: uuid.UUID):
        sql = """
        SELECT
          meal_entry_id,
          recipe_id::text AS recipe_id,
          day_index,
          servings
        FROM meal_entry
        WHERE plan_id = :pid
        ORDER BY day_index
        """
        rows = self.db.execute(text(sql), {"pid": str(plan_id)}).mappings().all()
        return [dict(r) for r in rows]