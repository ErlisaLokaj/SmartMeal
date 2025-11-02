"""Shopping list service"""

import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from datetime import datetime

from domain.models import (
    ShoppingList,
    ShoppingListItem,
    MealPlan,
    MealEntry,
    PantryItem,
    AppUser,
)
from repositories import (
    MealPlanRepository,
    MealEntryRepository,
    PantryRepository,
    ShoppingListRepository,
    ShoppingListItemRepository,
    RecipeRepository,
)

logger = logging.getLogger("smartmeal.shopping")


class ShoppingService:
    """Business logic for shopping list generation."""

    @staticmethod
    def build_list(db: Session, plan_id: UUID, user_id: UUID) -> ShoppingList:
        """
        Create a shopping list from a meal plan by calculating:
        needed_ingredients = meal_plan_requirements - pantry_inventory

        Algorithm:
        1. Load all meal entries for the plan
        2. Aggregate ingredients across all recipes (using MongoDB)
        3. Load user's current pantry
        4. Calculate difference (needed - available)
        5. Create shopping list with missing items

        Args:
            db: Database session
            plan_id: Meal plan UUID
            user_id: User UUID

        Returns:
            ShoppingList object with items

        Raises:
            ValueError: If plan not found or doesn't belong to user
        """
        logger.info(f"Building shopping list for plan {plan_id}, user {user_id}")

        # Initialize repositories
        meal_plan_repo = MealPlanRepository(db)
        meal_entry_repo = MealEntryRepository(db)
        pantry_repo = PantryRepository(db)

        # 1. Validate plan exists and belongs to user
        plan = meal_plan_repo.get_by_id_and_user(plan_id, user_id)

        if not plan:
            raise ValueError(
                f"Meal plan {plan_id} not found or doesn't belong to user {user_id}"
            )

        # 2. Load all meal entries for the plan
        entries = meal_entry_repo.get_by_plan_id(plan_id)

        if not entries:
            logger.warning(f"No meal entries found for plan {plan_id}")
            # Create empty shopping list
            return ShoppingService._create_empty_list(db, user_id, plan_id)

        logger.info(f"Found {len(entries)} meal entries in plan")

        # 3. Extract recipe IDs and servings
        recipe_ids = []
        servings_list = []

        for entry in entries:
            if entry.recipe_id:
                recipe_ids.append(str(entry.recipe_id))
                servings_list.append(float(entry.servings or 1))

        if not recipe_ids:
            logger.warning(f"No recipes found in meal entries for plan {plan_id}")
            return ShoppingService._create_empty_list(db, user_id, plan_id)

        logger.info(f"Aggregating ingredients from {len(recipe_ids)} recipes")

        # 4. Aggregate ingredients from MongoDB recipes
        recipe_repo = RecipeRepository()
        try:
            # Convert recipe_ids back to UUIDs for repository
            from uuid import UUID

            recipe_uuids = [UUID(rid) for rid in recipe_ids]
            aggregated = recipe_repo.aggregate_ingredients(
                recipe_ids=recipe_uuids, servings_list=servings_list
            )
        except Exception as e:
            logger.error(f"Failed to aggregate ingredients from MongoDB: {e}")
            raise ValueError("Failed to aggregate recipe ingredients")

        logger.info(f"Aggregated {len(aggregated)} unique ingredients")

        # 5. Load user's pantry
        pantry_items = pantry_repo.get_by_user_id(user_id)

        # Build pantry lookup: ingredient_id -> (quantity, unit)
        pantry_lookup = {}
        for item in pantry_items:
            key = str(item.ingredient_id)
            pantry_lookup[key] = {"quantity": float(item.quantity), "unit": item.unit}

        logger.info(f"Loaded {len(pantry_items)} pantry items")

        # 6. Calculate what's missing (needed - available)
        missing_items = ShoppingService._calculate_missing(
            aggregated=aggregated, pantry_lookup=pantry_lookup
        )

        logger.info(f"Calculated {len(missing_items)} missing ingredients")

        # 7. Create shopping list in database using repository
        shopping_list_repo = ShoppingListRepository(db)
        shopping_list_item_repo = ShoppingListItemRepository(db)

        shopping_list = ShoppingList(user_id=user_id, plan_id=plan_id, status="pending")
        shopping_list = shopping_list_repo.create(shopping_list)

        # 8. Add shopping list items
        list_items = []
        for item_data in missing_items:
            list_item = ShoppingListItem(
                list_id=shopping_list.list_id,
                ingredient_id=UUID(item_data["ingredient_id"]),
                ingredient_name=item_data.get("ingredient_name"),
                needed_qty=item_data["needed_qty"],
                unit=item_data["unit"],
                checked=False,
                from_recipe_id=(
                    UUID(item_data["from_recipe_id"])
                    if item_data.get("from_recipe_id")
                    else None
                ),
                note=None,
            )
            list_items.append(list_item)

        shopping_list_item_repo.bulk_create(list_items)

        logger.info(
            f"Shopping list created: list_id={shopping_list.list_id}, "
            f"items={len(missing_items)}"
        )

        return shopping_list

    @staticmethod
    def _calculate_missing(
        aggregated: Dict[str, Dict[str, Any]], pantry_lookup: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Calculate missing ingredients: needed - available.

        For simplicity, we assume unit compatibility. In production,
        you'd want unit conversion (e.g., kg to g, cups to ml).

        Args:
            aggregated: {ingredient_id: {total_quantity, unit, from_recipes, name}}
            pantry_lookup: {ingredient_id: {quantity, unit}}

        Returns:
            List of missing items with needed quantities
        """
        missing = []

        for ing_id, needed in aggregated.items():
            needed_qty = needed["total_quantity"]
            needed_unit = needed["unit"]

            # Check if we have this ingredient in pantry
            if ing_id in pantry_lookup:
                available = pantry_lookup[ing_id]
                available_qty = available["quantity"]
                available_unit = available["unit"]

                # Simple unit matching (should use proper conversion in production)
                if available_unit == needed_unit:
                    remaining = needed_qty - available_qty

                    if remaining > 0:
                        # Still need more
                        missing.append(
                            {
                                "ingredient_id": ing_id,
                                "ingredient_name": needed.get("name"),
                                "needed_qty": remaining,
                                "unit": needed_unit,
                                "from_recipe_id": (
                                    needed["from_recipes"][0]
                                    if needed["from_recipes"]
                                    else None
                                ),
                            }
                        )
                else:
                    # Units don't match - add to list (conservative approach)
                    logger.debug(
                        f"Unit mismatch for {ing_id}: needed {needed_unit}, "
                        f"have {available_unit}"
                    )
                    missing.append(
                        {
                            "ingredient_id": ing_id,
                            "ingredient_name": needed.get("name"),
                            "needed_qty": needed_qty,
                            "unit": needed_unit,
                            "from_recipe_id": (
                                needed["from_recipes"][0]
                                if needed["from_recipes"]
                                else None
                            ),
                        }
                    )
            else:
                # Not in pantry at all - need full amount
                missing.append(
                    {
                        "ingredient_id": ing_id,
                        "ingredient_name": needed.get("name"),
                        "needed_qty": needed_qty,
                        "unit": needed_unit,
                        "from_recipe_id": (
                            needed["from_recipes"][0]
                            if needed["from_recipes"]
                            else None
                        ),
                    }
                )

        return missing

    @staticmethod
    def _create_empty_list(db: Session, user_id: UUID, plan_id: UUID) -> ShoppingList:
        """Create an empty shopping list."""
        shopping_list_repo = ShoppingListRepository(db)
        shopping_list = ShoppingList(user_id=user_id, plan_id=plan_id, status="empty")
        return shopping_list_repo.create(shopping_list)

    @staticmethod
    def get_shopping_list(
        db: Session, list_id: UUID, user_id: UUID
    ) -> Optional[ShoppingList]:
        """Get a shopping list by ID (must belong to user)."""
        shopping_repo = ShoppingListRepository(db)
        return shopping_repo.get_by_id_and_user(list_id, user_id)

    @staticmethod
    def get_user_shopping_lists(
        db: Session, user_id: UUID, limit: int = 20
    ) -> List[ShoppingList]:
        """Get all shopping lists for a user."""
        shopping_repo = ShoppingListRepository(db)
        return shopping_repo.get_by_user_id(user_id, limit)

    @staticmethod
    def update_item_status(
        db: Session,
        list_item_id: UUID,
        checked: Optional[bool] = None,
        note: Optional[str] = None,
    ) -> Optional[ShoppingListItem]:
        """Update a shopping list item (check off or add note)."""
        item_repo = ShoppingListItemRepository(db)
        item = item_repo.get_by_id(list_item_id)

        if not item:
            return None

        if checked is not None:
            item.checked = checked

        if note is not None:
            item.note = note

        return item_repo.update(item)

    @staticmethod
    def delete_shopping_list(db: Session, list_id: UUID, user_id: UUID) -> bool:
        """Delete a shopping list (must belong to user)."""
        shopping_repo = ShoppingListRepository(db)
        deleted = shopping_repo.delete_by_id_and_user(list_id, user_id)

        if deleted:
            logger.info(f"Shopping list deleted: {list_id}")
            return True

        return False
