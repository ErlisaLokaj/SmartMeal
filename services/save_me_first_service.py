"""
Save-me-first Service - Prevents food waste by suggesting recipes for expiring ingredients.
Implements use case 10 (Save-me-first Suggestions).
"""

from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session
import logging
import uuid
from decimal import Decimal
from datetime import datetime, date, timedelta
from collections import Counter

from domain.schemas.save_me_first_schemas import (
    ExpiringIngredient,
    RecipeSuggestion,
    SaveMeFirstResponse,
    SaveMeFirstSettings,
)
from services.pantry_service import PantryService
from services.recipe_service import search_recipes
from repositories import (
    UserRepository,
    PantryRepository,
    IngredientRepository,
)
from app.exceptions import NotFoundError, ServiceValidationError

logger = logging.getLogger("smartmeal.save_me_first")


class SaveMeFirstService:
    @staticmethod
    def generate_suggestions(
        db: Session,
        user_id: uuid.UUID,
        days_threshold: int = 3,
        max_suggestions: int = 5,
    ) -> SaveMeFirstResponse:
        """
        Generate save-me-first suggestions for a user based on expiring pantry items.

        This is the main method that implements the food waste prevention use case:
        1. Find expiring pantry items
        2. Categorize by urgency (critical/urgent/soon)
        3. Search for recipes using these ingredients
        4. Rank recipes by match score, urgency, and user preferences
        5. Return top suggestions with actionable tips

        Args:
            db: Database session
            user_id: User's UUID
            days_threshold: Days before expiry to consider (default: 3)
            max_suggestions: Maximum number of recipe suggestions (default: 5)

        Returns:
            SaveMeFirstResponse with expiring items and recipe suggestions

        Raises:
            NotFoundError: If user not found
        """
        # Step 1: Verify user exists
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")

        logger.info(
            f"Generating save-me-first suggestions for user {user_id} "
            f"(threshold: {days_threshold} days, max: {max_suggestions})"
        )

        # Step 2: Get expiring pantry items
        expiring_items_raw = PantryService.get_expiring_soon(
            db, user_id, days_threshold
        )

        if not expiring_items_raw:
            logger.info(f"No expiring items found for user {user_id}")
            return SaveMeFirstResponse(
                user_id=user_id,
                generated_at=datetime.utcnow().isoformat(),
                expiring_ingredients=[],
                recipe_suggestions=[],
                total_expiring=0,
                critical_count=0,
                urgent_count=0,
                tips=SaveMeFirstService._get_general_tips(),
            )

        # Step 3: Enrich expiring items with ingredient names and urgency
        expiring_ingredients = SaveMeFirstService._enrich_expiring_items(
            expiring_items_raw
        )

        # Step 4: Categorize by urgency
        critical_count = sum(
            1 for ei in expiring_ingredients if ei.urgency_level == "critical"
        )
        urgent_count = sum(
            1 for ei in expiring_ingredients if ei.urgency_level == "urgent"
        )

        logger.info(
            f"Found {len(expiring_ingredients)} expiring items: "
            f"{critical_count} critical, {urgent_count} urgent"
        )

        # Step 5: Find recipes using expiring ingredients
        recipe_suggestions = SaveMeFirstService._find_matching_recipes(
            db, user_id, expiring_ingredients, max_suggestions
        )

        # Step 6: Generate personalized tips
        tips = SaveMeFirstService._generate_tips(
            expiring_ingredients, recipe_suggestions
        )

        return SaveMeFirstResponse(
            user_id=user_id,
            generated_at=datetime.utcnow().isoformat(),
            expiring_ingredients=expiring_ingredients,
            recipe_suggestions=recipe_suggestions,
            total_expiring=len(expiring_ingredients),
            critical_count=critical_count,
            urgent_count=urgent_count,
            tips=tips,
        )

    @staticmethod
    def _enrich_expiring_items(pantry_items) -> List[ExpiringIngredient]:
        """
        Enrich pantry items with ingredient names and urgency levels.

        Args:
            pantry_items: Raw pantry items from database

        Returns:
            List of enriched ExpiringIngredient objects
        """
        ingredient_repo = IngredientRepository()
        expiring_ingredients = []

        # Batch fetch ingredient metadata
        ingredient_ids = [str(item.ingredient_id) for item in pantry_items]
        try:
            metadata_map = ingredient_repo.get_ingredients_batch(ingredient_ids)
        except Exception as e:
            logger.warning(f"Could not fetch ingredient metadata: {e}")
            metadata_map = {}

        today = date.today()

        for item in pantry_items:
            # Calculate days until expiry
            days_until = 999  # Default for items without expiry
            if item.best_before:
                days_until = (item.best_before - today).days

            # Determine urgency level
            if days_until < 1:
                urgency = "critical"
            elif days_until <= 2:
                urgency = "urgent"
            else:
                urgency = "soon"

            # Get ingredient name
            meta = metadata_map.get(str(item.ingredient_id), {})
            ingredient_name = meta.get("name", "Unknown")

            expiring_ingredients.append(
                ExpiringIngredient(
                    pantry_item_id=item.pantry_item_id,
                    ingredient_id=item.ingredient_id,
                    ingredient_name=ingredient_name,
                    quantity=item.quantity,
                    unit=item.unit,
                    best_before=item.best_before,
                    days_until_expiry=max(0, days_until),
                    urgency_level=urgency,
                )
            )

        # Sort by urgency (critical first, then urgent, then soon)
        urgency_order = {"critical": 0, "urgent": 1, "soon": 2}
        expiring_ingredients.sort(
            key=lambda x: (urgency_order[x.urgency_level], x.days_until_expiry)
        )

        return expiring_ingredients

    @staticmethod
    def _find_matching_recipes(
        db: Session,
        user_id: uuid.UUID,
        expiring_ingredients: List[ExpiringIngredient],
        max_suggestions: int,
    ) -> List[RecipeSuggestion]:
        """
        Find recipes that use expiring ingredients.

        Strategy:
        1. Search for recipes containing expiring ingredients
        2. Check which recipes user can cook now (has all ingredients)
        3. Calculate match scores based on:
           - Number of expiring ingredients used
           - Urgency of ingredients (critical > urgent > soon)
           - User preferences and constraints
           - Recipe complexity/effort
        4. Rank and return top suggestions

        Args:
            db: Database session
            user_id: User's UUID
            expiring_ingredients: List of expiring ingredients
            max_suggestions: Maximum number of recipes to return

        Returns:
            List of RecipeSuggestion objects, ranked by relevance
        """
        if not expiring_ingredients:
            return []

        # Get user's full pantry for availability checking
        pantry_repo = PantryRepository(db)
        all_pantry_items = pantry_repo.get_by_user_id(user_id)
        pantry_ingredient_ids = {str(item.ingredient_id) for item in all_pantry_items}

        # Extract expiring ingredient IDs (prioritize by urgency)
        expiring_ids = [str(ei.ingredient_id) for ei in expiring_ingredients]

        # Search for recipes using expiring ingredients
        # We'll search multiple times with different ingredient combinations
        recipes_found = {}  # recipe_id -> recipe_dict

        # Search with critical ingredients first
        critical_ids = [
            str(ei.ingredient_id)
            for ei in expiring_ingredients
            if ei.urgency_level == "critical"
        ]
        if critical_ids:
            results = search_recipes(
                user_id=user_id,
                q=None,
                limit=20,
                offset=0,
                include_ingredient_ids=critical_ids[:3],  # Top 3 critical
            )
            for recipe in results:
                recipes_found[recipe["id"]] = recipe

        # Search with urgent + critical
        urgent_ids = [
            str(ei.ingredient_id)
            for ei in expiring_ingredients
            if ei.urgency_level in ("critical", "urgent")
        ]
        if urgent_ids and len(recipes_found) < max_suggestions * 2:
            results = search_recipes(
                user_id=user_id,
                q=None,
                limit=20,
                offset=0,
                include_ingredient_ids=urgent_ids[:5],  # Top 5 urgent
            )
            for recipe in results:
                recipes_found[recipe["id"]] = recipe

        # Search with all expiring ingredients
        if len(recipes_found) < max_suggestions * 2:
            results = search_recipes(
                user_id=user_id,
                q=None,
                limit=20,
                offset=0,
                include_ingredient_ids=expiring_ids[:10],
            )
            for recipe in results:
                recipes_found[recipe["id"]] = recipe

        if not recipes_found:
            logger.info(
                f"No recipes found using expiring ingredients for user {user_id}"
            )
            return []

        # Score and rank recipes
        scored_recipes = []
        expiring_ids_set = set(expiring_ids)

        for recipe in recipes_found.values():
            recipe_ingredient_ids = {
                ing.get("ingredient_id")
                for ing in recipe.get("ingredients", [])
                if ing.get("ingredient_id")
            }

            # Calculate matches
            uses_expiring = recipe_ingredient_ids & expiring_ids_set
            uses_expiring_count = len(uses_expiring)

            if uses_expiring_count == 0:
                continue  # Skip recipes that don't use any expiring ingredients

            # Get names of expiring ingredients used
            expiring_used_names = [
                ei.ingredient_name
                for ei in expiring_ingredients
                if str(ei.ingredient_id) in uses_expiring
            ]

            # Check if can cook now
            missing_ingredients = recipe_ingredient_ids - pantry_ingredient_ids
            missing_count = len(missing_ingredients)
            can_cook_now = missing_count == 0

            # Calculate scores
            match_score = SaveMeFirstService._calculate_match_score(
                recipe, uses_expiring_count, len(recipe_ingredient_ids), can_cook_now
            )

            urgency_score = SaveMeFirstService._calculate_urgency_score(
                expiring_ingredients, uses_expiring
            )

            effort_level = SaveMeFirstService._estimate_effort(recipe)

            scored_recipes.append(
                RecipeSuggestion(
                    recipe_id=recipe["id"],
                    recipe_name=recipe.get("name", "Unknown"),
                    cuisine=recipe.get("cuisine"),
                    total_time_minutes=recipe.get("total_time"),
                    servings=recipe.get("servings", 4),
                    uses_expiring_count=uses_expiring_count,
                    expiring_ingredients_used=expiring_used_names,
                    match_score=match_score,
                    urgency_score=urgency_score,
                    effort_level=effort_level,
                    missing_ingredients_count=missing_count,
                    can_cook_now=can_cook_now,
                )
            )

        # Sort by combined score (urgency * 0.6 + match * 0.4), then by can_cook_now
        scored_recipes.sort(
            key=lambda r: (
                -(r.urgency_score * 0.6 + r.match_score * 0.4),  # Higher is better
                not r.can_cook_now,  # Can cook now first
                r.missing_ingredients_count,  # Fewer missing is better
            )
        )

        return scored_recipes[:max_suggestions]

    @staticmethod
    def _calculate_match_score(
        recipe: Dict[str, Any],
        uses_expiring_count: int,
        total_ingredients: int,
        can_cook_now: bool,
    ) -> float:
        """
        Calculate how well a recipe matches the user's needs.

        Factors:
        - Percentage of recipe using expiring ingredients (higher is better)
        - Can cook now (bonus)
        - Recipe complexity (simpler is better for urgency)

        Returns:
            Score from 0-100
        """
        if total_ingredients == 0:
            return 0.0

        # Base score: percentage of recipe using expiring items
        base_score = (uses_expiring_count / total_ingredients) * 100

        # Bonus for being able to cook now
        if can_cook_now:
            base_score += 20

        # Cap at 100
        return min(100.0, base_score)

    @staticmethod
    def _calculate_urgency_score(
        expiring_ingredients: List[ExpiringIngredient], uses_expiring: set
    ) -> float:
        """
        Calculate urgency score based on which expiring ingredients are used.

        Critical ingredients (< 1 day) contribute more to urgency.

        Returns:
            Score from 0-100
        """
        if not uses_expiring:
            return 0.0

        total_urgency = 0
        urgency_weights = {"critical": 100, "urgent": 60, "soon": 30}

        for ei in expiring_ingredients:
            if str(ei.ingredient_id) in uses_expiring:
                total_urgency += urgency_weights.get(ei.urgency_level, 0)

        # Average urgency, capped at 100
        return min(100.0, total_urgency / len(uses_expiring))

    @staticmethod
    def _estimate_effort(recipe: Dict[str, Any]) -> str:
        """
        Estimate cooking effort based on recipe attributes.

        Returns:
            'easy', 'medium', or 'hard'
        """
        total_time = recipe.get("total_time", 0)
        ingredient_count = len(recipe.get("ingredients", []))

        # Simple heuristic
        if total_time <= 30 and ingredient_count <= 7:
            return "easy"
        elif total_time <= 60 and ingredient_count <= 12:
            return "medium"
        else:
            return "hard"

    @staticmethod
    def _generate_tips(
        expiring_ingredients: List[ExpiringIngredient],
        recipe_suggestions: List[RecipeSuggestion],
    ) -> List[str]:
        """Generate personalized waste prevention tips."""
        tips = []

        # Critical items warning
        critical = [ei for ei in expiring_ingredients if ei.urgency_level == "critical"]
        if critical:
            critical_names = ", ".join([ei.ingredient_name for ei in critical[:3]])
            if len(critical) > 3:
                critical_names += f" and {len(critical) - 3} more"
            tips.append(
                f"⚠️ URGENT: {critical_names} expiring today! Use immediately or freeze."
            )

        # Recipe suggestions tip
        if recipe_suggestions:
            cookable = [r for r in recipe_suggestions if r.can_cook_now]
            if cookable:
                tips.append(
                    f"✨ You can cook '{cookable[0].recipe_name}' right now using expiring ingredients!"
                )
            else:
                tips.append(
                    f"📝 Consider shopping for a few items to cook '{recipe_suggestions[0].recipe_name}'"
                )

        # General tips based on ingredient categories
        if len(expiring_ingredients) >= 5:
            tips.append(
                "💡 Tip: Freeze ingredients you can't use immediately to extend shelf life"
            )

        if not recipe_suggestions:
            tips.append(
                "🥗 No recipe matches found. Consider making a simple stir-fry or soup with expiring items"
            )

        tips.append("📅 Check your pantry regularly to stay ahead of expiring items")

        return tips

    @staticmethod
    def _get_general_tips() -> List[str]:
        """Get general waste prevention tips when no items are expiring."""
        return [
            "✅ Great! No items expiring soon in your pantry",
            "📅 Keep checking your pantry regularly to prevent waste",
            "💡 Use the FIFO method: First In, First Out",
            "🏷️ Label items with purchase dates to track freshness",
        ]
