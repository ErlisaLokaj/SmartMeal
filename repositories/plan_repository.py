from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session


class PlanRepository:
    """
    Repository layer for meal plan data access operations.
    Handles all database interactions for plans and meal entries.
    """

    def __init__(self, db: Session):
        self.db: Session = db

    def user_exists(self, user_id: uuid.UUID) -> bool:
        """Check if a user exists in the database."""
        sql = "SELECT 1 FROM app_user WHERE user_id = :uid LIMIT 1"
        row = self.db.execute(text(sql), {"uid": str(user_id)}).first()
        return bool(row)

    def load_pantry(self, user_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Load all pantry items for a specific user."""
        sql = """
        SELECT ingredient_id::text AS ingredient_id, quantity, unit, best_before
        FROM pantry_item
        WHERE user_id = :uid
        """
        rows = self.db.execute(text(sql), {"uid": str(user_id)}).mappings().all()
        return [dict(r) for r in rows]

    def insert_meal_plan(self, user_id: uuid.UUID, starts_on: date, ends_on: date) -> uuid.UUID:
        """
        Create a new meal plan record.

        Table: meal_plan(plan_id uuid pk, user_id uuid, starts_on date, ends_on date,
                        title text null, created_at timestamptz default now())
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

    def insert_meal_entry(self, plan_id: uuid.UUID, day_idx: int, recipe_id: str, servings: int = 2) -> None:
        """
        Create a new meal entry for a plan.

        Table: meal_entry(meal_entry_id uuid pk default gen_random_uuid(),
                         plan_id uuid fk -> meal_plan.plan_id,
                         recipe_id text, day_index int, servings int,
                         created_at timestamptz default now())
        """
        sql = """
        INSERT INTO meal_entry (plan_id, recipe_id, day_index, servings)
        VALUES (:pid, :rid, :dix, :srv)
        """
        self.db.execute(
            text(sql),
            {"pid": str(plan_id), "rid": str(recipe_id), "dix": day_idx, "srv": servings},
        )

    def list_user_plans(self, user_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Get all meal plans for a specific user with entry counts."""
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

    def get_plan_entries(self, plan_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Get all meal entries for a specific plan."""
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

    def commit(self) -> None:
        """Commit the current transaction."""
        self.db.commit()