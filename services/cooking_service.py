"""
Cooking Service - Handles recipe cooking, pantry decrement, and logging.
Implements use case 8 (Cook Recipe - Auto-Decrement).
"""

from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session
import logging
import uuid
from decimal import Decimal
from datetime import datetime, timedelta
from collections import Counter

from domain.models import AppUser, CookingLog
from domain.schemas.cooking_schemas import (
    IngredientShortage,
    NutritionalSummary,
    CookRecipeResponse,
    CookingLogEntry,
    CookingHistoryResponse,
    CookingStatsResponse,
)
from domain.schemas.recipe_shopping_schemas import (
    RecipeShoppingItem,
    RecipeShoppingListResponse,
)
from services.recipe_service import get_recipe_by_id
from repositories import (
    UserRepository,
    CookingLogRepository,
    PantryRepository,
    IngredientRepository,
)
from app.exceptions import NotFoundError, ServiceValidationError

logger = logging.getLogger("smartmeal.cooking")


class CookingService:
    @staticmethod
    def cook_recipe(
        db: Session, user_id: uuid.UUID, recipe_id: str, servings: int
    ) -> CookRecipeResponse:
        """
        Cook a recipe: validate, decrement pantry, log cooking, and return response.

        This implements the comprehensive "Cook Recipe (Auto-Decrement)" use case
        with full validation, FIFO pantry management, and enhanced user feedback.

        Flow:
        1. Verify user exists
        2. Retrieve and validate recipe from MongoDB
        3. Check for allergy conflicts
        4. Validate all ingredients in batch (Neo4j)
        5. Decrement pantry items (FIFO, transaction-safe)
        6. Log cooking activity
        7. Generate comprehensive response with tips and insights

        Args:
            db: Database session
            user_id: User's UUID
            recipe_id: Recipe ID (string from MongoDB)
            servings: Number of servings (1-20)

        Returns:
            CookRecipeResponse with detailed cooking results, shortages, nutrition, tips

        Raises:
            NotFoundError: If user or recipe not found
            ServiceValidationError: If validation fails (allergies, ingredients, etc.)
        """
        # Step 1: Verify user exists
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")

        # Step 2: Get and validate recipe from MongoDB
        recipe = get_recipe_by_id(recipe_id)
        if not recipe:
            raise ServiceValidationError(f"Recipe {recipe_id} not found")

        recipe_name = recipe.get("name", "Unknown Recipe")
        ingredients = recipe.get("ingredients", [])

        if not ingredients:
            raise ServiceValidationError(
                f"Recipe '{recipe_name}' has no ingredients listed"
            )

        logger.info(
            f"User {user_id} cooking '{recipe_name}' for {servings} servings "
            f"({len(ingredients)} ingredients)"
        )

        # Step 3: Validate recipe suitability for user (allergies)
        CookingService._validate_recipe_for_user(db, user_id, recipe)

        # Step 4: Validate all ingredients exist in Neo4j (batch)
        ingredient_ids = [uuid.UUID(ing["ingredient_id"]) for ing in ingredients]
        ingredient_metadata = CookingService._validate_ingredients_batch(ingredient_ids)

        # Step 5: Check pantry availability BEFORE attempting to cook
        shortages = CookingService._check_pantry_availability(
            db, user_id, recipe, servings, ingredient_metadata
        )

        if shortages:
            # User doesn't have all ingredients - cannot cook
            shortage_list = ", ".join([s.ingredient_name for s in shortages[:3]])
            if len(shortages) > 3:
                shortage_list += f" and {len(shortages) - 3} more"

            raise ServiceValidationError(
                f"Cannot cook '{recipe_name}': Missing ingredients in pantry ({shortage_list}). "
                f"Please add these ingredients to your pantry or create a shopping list first."
            )

        # Step 6: Decrement pantry with FIFO logic (we know we have everything)
        try:
            CookingService._decrement_pantry_for_recipe(
                db, user_id, recipe, servings, ingredient_metadata
            )

            # Step 7: Log the cooking
            cooking_repo = CookingLogRepository(db)
            cooking_log = cooking_repo.create_cooking_log(
                user_id=user_id, recipe_id=recipe_id, servings=servings
            )
            logger.info(
                f"Cooking logged: {cooking_log.cook_id} " f"for recipe '{recipe_name}'"
            )

            db.commit()

            # Step 8: Generate comprehensive response (no shortages since we validated)
            return CookingService._generate_cook_response(
                recipe, servings, [], ingredient_metadata  # Empty shortages list
            )

        except Exception as e:
            db.rollback()
            logger.error(
                f"Error cooking recipe '{recipe_name}' for user {user_id}: {e}"
            )
            raise ServiceValidationError(f"Failed to process cooking: {e}")

    @staticmethod
    def _validate_recipe_for_user(
        db: Session, user_id: uuid.UUID, recipe: Dict[str, Any]
    ) -> None:
        """
        Validate if recipe is suitable for user based on allergies.

        Args:
            db: Database session
            user_id: User's UUID
            recipe: Recipe dict with ingredients

        Raises:
            ServiceValidationError: If recipe contains allergens
        """
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(user_id)
        if not user or not user.allergies:
            return  # No allergies to check

        # Check allergies
        user_allergen_ids = {str(allergy.ingredient_id) for allergy in user.allergies}
        recipe_ingredient_ids = {
            ing.get("ingredient_id") for ing in recipe.get("ingredients", [])
        }

        conflicting_allergens = user_allergen_ids & recipe_ingredient_ids
        if conflicting_allergens:
            raise ServiceValidationError(
                f"Recipe contains allergens for this user: "
                f"{', '.join(conflicting_allergens)}. "
                f"Cannot proceed with cooking for safety reasons."
            )

        logger.info(f"Allergy validation passed for user {user_id}")

    @staticmethod
    def _validate_ingredients_batch(
        ingredient_ids: List[uuid.UUID],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Validate all recipe ingredients exist in Neo4j in a single batch query.

        Args:
            ingredient_ids: List of ingredient UUIDs

        Returns:
            Dict mapping ingredient_id (str) to metadata dict

        Raises:
            ServiceValidationError: If Neo4j unavailable or ingredients not found
        """
        if not ingredient_ids:
            return {}

        ingredient_repo = IngredientRepository()
        try:
            id_strings = [str(iid) for iid in ingredient_ids]
            meta_map = ingredient_repo.get_ingredients_batch(id_strings)
            logger.info(f"Validated {len(meta_map)} ingredients in batch")
            return meta_map
        except RuntimeError as e:
            raise ServiceValidationError(
                f"Cannot validate ingredients: Neo4j database not available. {e}"
            )
        except ValueError as e:
            raise ServiceValidationError(f"Some ingredients not found in catalog: {e}")

    @staticmethod
    def _check_pantry_availability(
        db: Session,
        user_id: uuid.UUID,
        recipe: Dict[str, Any],
        servings: int,
        ingredient_metadata: Dict[str, Dict[str, Any]],
    ) -> List[IngredientShortage]:
        """
        Check if user has all required ingredients in pantry WITHOUT modifying it.

        This is a read-only check to validate before cooking.

        Args:
            db: Database session
            user_id: User's UUID
            recipe: Recipe dict with ingredients
            servings: Number of servings
            ingredient_metadata: Ingredient metadata from Neo4j

        Returns:
            List of IngredientShortage objects for missing/insufficient items
            Empty list if user has everything needed
        """
        ingredients = recipe.get("ingredients", [])
        pantry_repo = PantryRepository(db)
        shortages = []

        for ingredient in ingredients:
            ingredient_id = uuid.UUID(ingredient["ingredient_id"])
            base_qty = Decimal(str(ingredient.get("quantity", 0)))
            required_qty = base_qty * servings
            unit = ingredient.get("unit", "")

            # Get pantry items for this ingredient (read-only)
            pantry_items = pantry_repo.get_items_for_decrement(
                user_id, ingredient_id, unit
            )

            # Calculate total available
            available_qty = sum(Decimal(str(item.quantity)) for item in pantry_items)

            # Check if we have enough
            if available_qty < required_qty:
                meta = ingredient_metadata.get(str(ingredient_id), {})
                shortage = IngredientShortage(
                    ingredient_id=ingredient_id,
                    ingredient_name=meta.get("name", "Unknown"),
                    needed_quantity=required_qty,
                    available_quantity=available_qty,
                    deficit_quantity=required_qty - available_qty,
                    unit=unit,
                )
                shortages.append(shortage)
                logger.debug(
                    f"Shortage detected for '{shortage.ingredient_name}': "
                    f"need {required_qty} {unit}, have {available_qty} {unit}"
                )

        return shortages

    @staticmethod
    def _decrement_pantry_for_recipe(
        db: Session,
        user_id: uuid.UUID,
        recipe: Dict[str, Any],
        servings: int,
        ingredient_metadata: Dict[str, Dict[str, Any]],
    ) -> None:
        """
        Decrement pantry quantities for recipe ingredients using FIFO logic.

        This implements batch-aware FIFO inventory management:
        - Consumes oldest items first (based on best_before date)
        - Handles multiple pantry batches per ingredient
        - Auto-removes items when quantity reaches 0

        IMPORTANT: This method assumes availability has been pre-checked.
        It will not fail if shortages occur (defensive programming).

        Args:
            db: Database session
            user_id: User's UUID
            recipe: Recipe dict with ingredients
            servings: Number of servings
            ingredient_metadata: Ingredient metadata from Neo4j

        Note:
            This method assumes it's called within a transaction that will be
            committed or rolled back by the caller.
        """
        ingredients = recipe.get("ingredients", [])
        pantry_repo = PantryRepository(db)
        shortages = []

        for ingredient in ingredients:
            ingredient_id = uuid.UUID(ingredient["ingredient_id"])
            base_qty = Decimal(str(ingredient.get("quantity", 0)))
            required_qty = base_qty * servings
            unit = ingredient.get("unit", "")

            # Get pantry items for this ingredient, ordered by expiry (FIFO)
            pantry_items = pantry_repo.get_items_for_decrement(
                user_id, ingredient_id, unit
            )

            # Track what we have available
            available_qty = sum(item.quantity for item in pantry_items)
            remaining_needed = required_qty

            # Consume from pantry items (oldest first)
            for item in pantry_items:
                if remaining_needed <= 0:
                    break

                available_in_item = Decimal(str(item.quantity))
                to_decrement = min(available_in_item, remaining_needed)

                new_qty = available_in_item - to_decrement

                if new_qty == 0:
                    # Auto-remove when fully consumed
                    pantry_repo.delete_by_id(item.pantry_item_id)
                    logger.debug(
                        f"Removed pantry item {item.pantry_item_id} "
                        f"(ingredient {ingredient_id}, fully consumed)"
                    )
                else:
                    # Partial consumption
                    pantry_repo.update_quantity(item.pantry_item_id, new_qty)
                    logger.debug(
                        f"Decremented pantry item {item.pantry_item_id}: "
                        f"{available_in_item} → {new_qty}"
                    )

                remaining_needed -= to_decrement

            # Defensive check - this should not happen if pre-check was done
            if remaining_needed > 0:
                logger.warning(
                    f"Unexpected shortage for ingredient {ingredient_id}: "
                    f"needed {required_qty} {unit}, had {available_qty} {unit}"
                )

        logger.info("Pantry decremented successfully for all ingredients")

    @staticmethod
    def _generate_cook_response(
        recipe: Dict[str, Any],
        servings: int,
        shortages: List[IngredientShortage],
        ingredient_metadata: Dict[str, Dict[str, Any]],
    ) -> CookRecipeResponse:
        """
        Generate comprehensive cooking response with tips and insights.

        Args:
            recipe: Recipe dict
            servings: Number of servings
            shortages: List of ingredient shortages
            ingredient_metadata: Ingredient metadata from Neo4j

        Returns:
            CookRecipeResponse with all details
        """
        recipe_name = recipe.get("name", "Unknown Recipe")

        # Nutritional summary
        nutritional_summary = None
        if "nutrition" in recipe and recipe["nutrition"]:
            base_nutrition = recipe["nutrition"]
            nutritional_summary = NutritionalSummary(
                calories_per_serving=(
                    base_nutrition.get("calories", 0) / servings if servings > 0 else 0
                ),
                protein_g=base_nutrition.get("protein", 0),
                carbs_g=base_nutrition.get("carbs", 0),
                fat_g=base_nutrition.get("fat", 0),
                fiber_g=base_nutrition.get("fiber"),
                sodium_mg=base_nutrition.get("sodium"),
            )

        # Waste prevention tips
        waste_prevention_tips = [
            "Store leftovers in airtight containers within 2 hours of cooking",
            "Label containers with date and contents for easy identification",
            "Use leftovers within 3-4 days or freeze for up to 3 months",
            "Plan meals to use similar ingredients across multiple recipes",
        ]

        # Personalized suggestions
        suggestions = []
        cuisine = recipe.get("cuisine")
        if cuisine:
            suggestions.append(f"Enjoyed this? Try exploring more {cuisine} recipes!")

        # Add shortage-based suggestions
        if shortages:
            shortage_names = [s.ingredient_name for s in shortages[:3]]
            suggestions.append(
                f"Consider adding {', '.join(shortage_names)} to your shopping list"
            )
        else:
            suggestions.append(
                "Great! You had all ingredients needed. Your pantry is well-stocked!"
            )

        # Cuisine-specific tips
        if cuisine:
            cuisine_lower = cuisine.lower()
            if "italian" in cuisine_lower:
                waste_prevention_tips.append(
                    "Freeze leftover pasta sauce in ice cube trays for quick meals"
                )
            elif "asian" in cuisine_lower or "chinese" in cuisine_lower:
                waste_prevention_tips.append(
                    "Use leftover rice to make fried rice within 1-2 days"
                )
            elif "mexican" in cuisine_lower:
                waste_prevention_tips.append(
                    "Leftover beans and rice make excellent burrito fillings"
                )

        # Success message
        if shortages:
            message = (
                f"Cooked '{recipe_name}' for {servings} servings, "
                f"but {len(shortages)} ingredients were short in your pantry"
            )
        else:
            message = f"Successfully cooked '{recipe_name}' for {servings} servings!"

        return CookRecipeResponse(
            success=True,
            message=message,
            recipe_name=recipe_name,
            servings=servings,
            pantry_updated=True,
            shortages=shortages,
            nutritional_summary=nutritional_summary,
            waste_prevention_tips=waste_prevention_tips[:5],  # Top 5 tips
            suggestions=suggestions,
        )

    @staticmethod
    def get_cooking_history(
        db: Session, user_id: uuid.UUID, days: int = 7
    ) -> CookingHistoryResponse:
        """
        Get cooking history for a user over specified days.

        Args:
            db: Database session
            user_id: User's UUID
            days: Number of days to look back (default: 7)

        Returns:
            CookingHistoryResponse with enriched cooking logs

        Raises:
            NotFoundError: If user not found
        """
        # Verify user exists
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")

        # Get cooking logs
        cooking_repo = CookingLogRepository(db)
        logs = cooking_repo.get_recent_logs(user_id, days)

        # Enrich logs with recipe details
        entries = []
        recipe_counter = Counter()

        for log in logs:
            recipe = get_recipe_by_id(log.recipe_id)
            recipe_name = recipe.get("name", "Unknown Recipe") if recipe else "Unknown"
            cuisine = recipe.get("cuisine") if recipe else None

            entries.append(
                CookingLogEntry(
                    cook_id=log.cook_id,
                    recipe_id=log.recipe_id,
                    recipe_name=recipe_name,
                    cuisine=cuisine,
                    servings=log.servings,
                    cooked_at=log.cooked_at,
                )
            )

            recipe_counter[log.recipe_id] += 1

        # Find favorite recipes
        favorite_recipes = None
        if recipe_counter:
            top_recipes = recipe_counter.most_common(3)
            favorite_recipes = []
            for recipe_id, count in top_recipes:
                recipe = get_recipe_by_id(recipe_id)
                if recipe:
                    favorite_recipes.append(
                        {
                            "recipe_id": recipe_id,
                            "recipe_name": recipe.get("name", "Unknown"),
                            "times_cooked": count,
                        }
                    )

        return CookingHistoryResponse(
            total_count=len(entries),
            entries=entries,
            period_days=days,
            favorite_recipes=favorite_recipes,
        )

    @staticmethod
    def get_cooking_stats(db: Session, user_id: uuid.UUID) -> CookingStatsResponse:
        """
        Get comprehensive cooking statistics for a user.

        Args:
            db: Database session
            user_id: User's UUID

        Returns:
            CookingStatsResponse with cooking statistics

        Raises:
            NotFoundError: If user not found
        """
        # Verify user exists
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")

        # Get all cooking logs
        cooking_repo = CookingLogRepository(db)
        all_logs = db.query(CookingLog).filter(CookingLog.user_id == user_id).all()

        total_recipes_cooked = len(all_logs)
        total_servings_cooked = sum(log.servings for log in all_logs)
        unique_recipes = len(set(log.recipe_id for log in all_logs))

        # Find most cooked recipe
        recipe_counter = Counter(log.recipe_id for log in all_logs)
        most_cooked_recipe = None
        if recipe_counter:
            most_cooked_id, count = recipe_counter.most_common(1)[0]
            recipe = get_recipe_by_id(most_cooked_id)
            if recipe:
                most_cooked_recipe = {
                    "recipe_id": most_cooked_id,
                    "recipe_name": recipe.get("name", "Unknown"),
                    "times_cooked": count,
                }

        # Find favorite cuisine
        cuisine_counter = Counter()
        for log in all_logs:
            recipe = get_recipe_by_id(log.recipe_id)
            if recipe and recipe.get("cuisine"):
                cuisine_counter[recipe["cuisine"]] += 1

        favorite_cuisine = None
        if cuisine_counter:
            favorite_cuisine = cuisine_counter.most_common(1)[0][0]

        # Recent activity
        recent_logs = cooking_repo.get_recent_logs(user_id, 30)
        recent_activity_days = len(set(log.cooked_at.date() for log in recent_logs))

        return CookingStatsResponse(
            total_recipes_cooked=total_recipes_cooked,
            total_servings_cooked=total_servings_cooked,
            unique_recipes=unique_recipes,
            favorite_cuisine=favorite_cuisine,
            recent_activity_days=recent_activity_days,
            most_cooked_recipe=most_cooked_recipe,
        )

    @staticmethod
    def generate_recipe_shopping_list(
        db: Session, user_id: uuid.UUID, recipe_id: str, servings: int
    ) -> RecipeShoppingListResponse:
        """
        Generate a shopping list for a specific recipe based on what's missing in pantry.

        This allows users to:
        1. Choose a recipe they want to cook
        2. See what ingredients they need to buy
        3. Shop for missing ingredients
        4. Then cook the recipe once they have everything

        Args:
            db: Database session
            user_id: User's UUID
            recipe_id: Recipe ID (string from MongoDB)
            servings: Number of servings to prepare

        Returns:
            RecipeShoppingListResponse with missing ingredients

        Raises:
            NotFoundError: If user or recipe not found
            ServiceValidationError: If validation fails
        """
        # Step 1: Verify user exists
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")

        # Step 2: Get and validate recipe
        recipe = get_recipe_by_id(recipe_id)
        if not recipe:
            raise ServiceValidationError(f"Recipe {recipe_id} not found")

        recipe_name = recipe.get("name", "Unknown Recipe")
        ingredients = recipe.get("ingredients", [])

        if not ingredients:
            raise ServiceValidationError(
                f"Recipe '{recipe_name}' has no ingredients listed"
            )

        logger.info(
            f"Generating shopping list for '{recipe_name}' "
            f"({servings} servings) for user {user_id}"
        )

        # Step 3: Validate ingredients exist in Neo4j
        ingredient_ids = [uuid.UUID(ing["ingredient_id"]) for ing in ingredients]
        ingredient_metadata = CookingService._validate_ingredients_batch(ingredient_ids)

        # Step 4: Check what's missing from pantry
        pantry_repo = PantryRepository(db)
        missing_items = []

        for ingredient in ingredients:
            ingredient_id = uuid.UUID(ingredient["ingredient_id"])
            base_qty = Decimal(str(ingredient.get("quantity", 0)))
            required_qty = base_qty * servings
            unit = ingredient.get("unit", "")

            # Get current pantry stock
            pantry_items = pantry_repo.get_items_for_decrement(
                user_id, ingredient_id, unit
            )
            available_qty = sum(Decimal(str(item.quantity)) for item in pantry_items)

            # Calculate how much to buy
            if available_qty < required_qty:
                to_buy = required_qty - available_qty
                meta = ingredient_metadata.get(str(ingredient_id), {})

                missing_items.append(
                    RecipeShoppingItem(
                        ingredient_id=ingredient_id,
                        ingredient_name=meta.get("name", "Unknown"),
                        needed_quantity=required_qty,
                        available_quantity=available_qty,
                        to_buy_quantity=to_buy,
                        unit=unit,
                    )
                )

        has_all = len(missing_items) == 0

        logger.info(
            f"Shopping list for '{recipe_name}': "
            f"{len(missing_items)} items needed, "
            f"can_cook_now={has_all}"
        )

        return RecipeShoppingListResponse(
            recipe_id=recipe_id,
            recipe_name=recipe_name,
            servings=servings,
            missing_items=missing_items,
            has_all_ingredients=has_all,
            total_items_needed=len(missing_items),
            can_cook_now=has_all,
        )
