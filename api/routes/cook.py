"""
Cook routes - Recipe cooking and pantry auto-decrement endpoints.
Implements use case 8 (Cook Recipe - Auto-Decrement).
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
import logging
from uuid import UUID

from domain.models import get_db_session
from domain.schemas.cooking_schemas import (
    CookRecipeRequest,
    CookRecipeResponse,
    CookingHistoryResponse,
    CookingStatsResponse,
)
from domain.schemas.recipe_shopping_schemas import (
    RecipeShoppingListRequest,
    RecipeShoppingListResponse,
)
from services.cooking_service import CookingService
from app.exceptions import NotFoundError, ServiceValidationError

router = APIRouter(prefix="/cook", tags=["Cooking"])
logger = logging.getLogger("smartmeal.api.cook")


@router.post("", response_model=CookRecipeResponse, status_code=status.HTTP_200_OK)
def cook_recipe_endpoint(
    request: CookRecipeRequest, db: Session = Depends(get_db_session)
) -> CookRecipeResponse:
    """
    Mark a recipe as cooked and automatically decrement pantry items.

    This endpoint implements the comprehensive Cook Recipe (Auto-Decrement) use case:
    1. Validates user and recipe exist
    2. Checks for allergy conflicts
    3. Validates all ingredients exist in catalog (Neo4j batch query)
    4. Decrements pantry items using FIFO logic (oldest items first)
    5. Auto-removes pantry items when quantity reaches 0
    6. Logs the cooking activity
    7. Returns comprehensive feedback including:
       - Recipe details and servings
       - Pantry update status
       - Any ingredient shortages
       - Nutritional summary
       - Waste prevention tips
       - Personalized suggestions

    **FIFO Pantry Management:**
    - Consumes oldest items first (based on best_before date)
    - Handles multiple pantry batches per ingredient
    - Transaction-safe (rollback on any error)

    **Error Handling:**
    - 400: Allergy conflict, ingredient validation failed
    - 404: User or recipe not found
    - 422: Invalid request payload (servings out of range, etc.)
    - 503: MongoDB unavailable

    Args:
        request: CookRecipeRequest with user_id, recipe_id, servings
        db: Database session (injected)

    Returns:
        CookRecipeResponse with comprehensive cooking results

    Example:
        ```json
        POST /cook
        {
          "user_id": "123e4567-e89b-12d3-a456-426614174000",
          "recipe_id": "507f1f77bcf86cd799439011",
          "servings": 4
        }
        ```

        Response:
        ```json
        {
          "success": true,
          "message": "Successfully cooked Spaghetti Carbonara for 4 servings!",
          "recipe_name": "Spaghetti Carbonara",
          "servings": 4,
          "pantry_updated": true,
          "shortages": [],
          "nutritional_summary": {
            "calories_per_serving": 450,
            "protein_g": 18,
            "carbs_g": 52,
            "fat_g": 16
          },
          "waste_prevention_tips": [
            "Store leftovers in airtight containers within 2 hours",
            "Label containers with date and contents"
          ],
          "suggestions": [
            "Enjoyed this? Try exploring more Italian recipes!"
          ]
        }
        ```
    """
    try:
        # Validate and convert UUIDs
        try:
            user_uuid = UUID(request.user_id)
        except ValueError:
            raise ServiceValidationError(f"Invalid user_id format: {request.user_id}")

        # Recipe ID is kept as string (MongoDB ObjectId or UUID string)
        result = CookingService.cook_recipe(
            db=db,
            user_id=user_uuid,
            recipe_id=request.recipe_id,
            servings=request.servings,
        )

        logger.info(
            f"Recipe '{result.recipe_name}' cooked successfully for user {user_uuid}"
        )

        return result

    except (NotFoundError, ServiceValidationError) as e:
        logger.error(f"Error cooking recipe: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error cooking recipe: {e}")
        raise


@router.get(
    "/history", response_model=CookingHistoryResponse, status_code=status.HTTP_200_OK
)
def get_cooking_history(
    user_id: UUID = Query(..., description="User ID to get cooking history for"),
    days: int = Query(
        7, ge=1, le=365, description="Number of days to look back (default: 7)"
    ),
    db: Session = Depends(get_db_session),
) -> CookingHistoryResponse:
    """
    Get cooking history for a user over a specified time period.

    Returns a list of all recipes cooked by the user within the specified
    number of days, enriched with recipe details from MongoDB.

    Args:
        user_id: UUID of the user
        days: Number of days to look back (1-365, default: 7)
        db: Database session (injected)

    Returns:
        CookingHistoryResponse with cooking logs and favorite recipes

    Raises:
        404: If user not found

    Example:
        ```
        GET /cook/history?user_id=123e4567-e89b-12d3-a456-426614174000&days=30
        ```

        Response:
        ```json
        {
          "total_count": 15,
          "entries": [
            {
              "cooking_log_id": "...",
              "recipe_id": "...",
              "recipe_name": "Spaghetti Carbonara",
              "cuisine": "Italian",
              "servings": 4,
              "cooked_at": "2025-11-05T18:30:00"
            }
          ],
          "period_days": 30,
          "favorite_recipes": [
            {
              "recipe_id": "...",
              "recipe_name": "Spaghetti Carbonara",
              "times_cooked": 5
            }
          ]
        }
        ```
    """
    try:
        history = CookingService.get_cooking_history(db, user_id, days)

        logger.info(
            f"Retrieved {history.total_count} cooking logs for user {user_id} "
            f"(last {days} days)"
        )

        return history

    except NotFoundError as e:
        logger.error(f"Error retrieving cooking history: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error retrieving cooking history: {e}")
        raise


@router.get(
    "/stats", response_model=CookingStatsResponse, status_code=status.HTTP_200_OK
)
def get_cooking_stats(
    user_id: UUID = Query(..., description="User ID to get cooking stats for"),
    db: Session = Depends(get_db_session),
) -> CookingStatsResponse:
    """
    Get comprehensive cooking statistics for a user.

    Returns aggregate statistics about the user's cooking activity:
    - Total recipes cooked
    - Total servings prepared
    - Number of unique recipes tried
    - Favorite cuisine
    - Most frequently cooked recipe
    - Recent activity level

    Args:
        user_id: UUID of the user
        db: Database session (injected)

    Returns:
        CookingStatsResponse with cooking statistics

    Raises:
        404: If user not found

    Example:
        ```
        GET /cook/stats?user_id=123e4567-e89b-12d3-a456-426614174000
        ```

        Response:
        ```json
        {
          "total_recipes_cooked": 42,
          "total_servings_cooked": 168,
          "unique_recipes": 28,
          "favorite_cuisine": "Italian",
          "recent_activity_days": 15,
          "most_cooked_recipe": {
            "recipe_id": "...",
            "recipe_name": "Spaghetti Carbonara",
            "times_cooked": 8
          }
        }
        ```
    """
    try:
        stats = CookingService.get_cooking_stats(db, user_id)

        logger.info(f"Retrieved cooking stats for user {user_id}")

        return stats

    except NotFoundError as e:
        logger.error(f"Error retrieving cooking stats: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error retrieving cooking stats: {e}")
        raise


@router.post(
    "/shopping-list",
    response_model=RecipeShoppingListResponse,
    status_code=status.HTTP_200_OK,
)
def generate_recipe_shopping_list(
    request: RecipeShoppingListRequest, db: Session = Depends(get_db_session)
) -> RecipeShoppingListResponse:
    """
    Generate a shopping list for a specific recipe.

    This endpoint helps users plan ahead by showing what ingredients they need
    to buy before they can cook a recipe. Users MUST have all ingredients in
    their pantry before they can cook the recipe.

    **Workflow:**
    1. User selects a recipe they want to cook
    2. System checks their pantry
    3. Returns list of missing ingredients
    4. User shops for missing items
    5. User adds purchased items to pantry
    6. User can then cook the recipe (if `can_cook_now` is true)

    **Strict Cooking Rule:**
    - Cooking will FAIL if any ingredient is missing from pantry
    - Use this endpoint to check before attempting to cook
    - Add all missing items to pantry first

    Args:
        request: RecipeShoppingListRequest with user_id, recipe_id, servings
        db: Database session (injected)

    Returns:
        RecipeShoppingListResponse with list of items to buy

    Raises:
        400: Validation error
        404: User or recipe not found

    Example:
        ```json
        POST /cook/shopping-list
        {
          "user_id": "123e4567-e89b-12d3-a456-426614174000",
          "recipe_id": "507f1f77bcf86cd799439011",
          "servings": 4
        }
        ```

        Response:
        ```json
        {
          "recipe_id": "507f1f77bcf86cd799439011",
          "recipe_name": "Spaghetti Carbonara",
          "servings": 4,
          "missing_items": [
            {
              "ingredient_id": "...",
              "ingredient_name": "Parmesan Cheese",
              "needed_quantity": 200,
              "available_quantity": 50,
              "to_buy_quantity": 150,
              "unit": "g"
            }
          ],
          "has_all_ingredients": false,
          "total_items_needed": 1,
          "can_cook_now": false
        }
        ```
    """
    try:
        # Validate and convert UUID
        try:
            user_uuid = UUID(request.user_id)
        except ValueError:
            raise ServiceValidationError(f"Invalid user_id format: {request.user_id}")

        shopping_list = CookingService.generate_recipe_shopping_list(
            db=db,
            user_id=user_uuid,
            recipe_id=request.recipe_id,
            servings=request.servings,
        )

        logger.info(
            f"Generated shopping list for recipe '{shopping_list.recipe_name}': "
            f"{shopping_list.total_items_needed} items needed"
        )

        return shopping_list

    except (NotFoundError, ServiceValidationError) as e:
        logger.error(f"Error generating shopping list: {e}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error generating shopping list: {e}")
        raise
