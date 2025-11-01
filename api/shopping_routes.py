"""API routes for shopping list management."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import logging

from core.database.models import get_db
from core.schemas.shopping_schemas import (
    ShoppingListCreate,
    ShoppingListResponse,
    ShoppingListItemResponse,
    ShoppingListItemUpdate
)
from core.services.shopping_service import ShoppingService

router = APIRouter(prefix="/shopping-lists", tags=["Shopping Lists"])
logger = logging.getLogger("smartmeal.api.shopping")


@router.post("", response_model=ShoppingListResponse, status_code=status.HTTP_201_CREATED)
def create_shopping_list(
        request: ShoppingListCreate,
        db: Session = Depends(get_db)
):
    """
    Create a shopping list from a meal plan.

    This implements Use Case 6: Create Shopping List

    Algorithm:
    1. Load meal entries from the plan
    2. Aggregate ingredients across all recipes (from MongoDB)
    3. Load user's pantry items
    4. Calculate missing = needed - available
    5. Create shopping list with missing items

    Example request:
    ```json
    {
        "plan_id": "123e4567-e89b-12d3-a456-426614174000",
        "user_id": "123e4567-e89b-12d3-a456-426614174001"
    }
    ```
    """
    try:
        shopping_list = ShoppingService.build_list(
            db=db,
            plan_id=request.plan_id,
            user_id=request.user_id
        )

        # Convert to response format
        return _to_response(shopping_list)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating shopping list: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create shopping list"
        )


@router.get("/{list_id}", response_model=ShoppingListResponse)
def get_shopping_list(
        list_id: UUID,
        user_id: UUID = Query(..., description="User ID for authorization"),
        db: Session = Depends(get_db)
):
    """
    Get a shopping list by ID.

    The shopping list must belong to the specified user.
    """
    shopping_list = ShoppingService.get_shopping_list(
        db=db,
        list_id=list_id,
        user_id=user_id
    )

    if not shopping_list:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shopping list {list_id} not found"
        )

    return _to_response(shopping_list)


@router.get("", response_model=List[ShoppingListResponse])
def get_user_shopping_lists(
        user_id: UUID = Query(..., description="User ID"),
        limit: int = Query(default=20, ge=1, le=100),
        db: Session = Depends(get_db)
):
    """
    Get all shopping lists for a user.

    Returns lists ordered by creation date (newest first).
    """
    shopping_lists = ShoppingService.get_user_shopping_lists(
        db=db,
        user_id=user_id,
        limit=limit
    )

    return [_to_response(sl) for sl in shopping_lists]


@router.patch("/items/{list_item_id}", response_model=ShoppingListItemResponse)
def update_shopping_list_item(
        list_item_id: UUID,
        update: ShoppingListItemUpdate,
        db: Session = Depends(get_db)
):
    """
    Update a shopping list item (check it off or add a note).

    Example request:
    ```json
    {
        "checked": true,
        "note": "Get organic version"
    }
    ```
    """
    item = ShoppingService.update_item_status(
        db=db,
        list_item_id=list_item_id,
        checked=update.checked,
        note=update.note
    )

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shopping list item {list_item_id} not found"
        )

    return ShoppingListItemResponse.model_validate(item)


@router.delete("/{list_id}")
def delete_shopping_list(
        list_id: UUID,
        user_id: UUID = Query(..., description="User ID for authorization"),
        db: Session = Depends(get_db)
):
    """
    Delete a shopping list.

    The shopping list must belong to the specified user.
    """
    success = ShoppingService.delete_shopping_list(
        db=db,
        list_id=list_id,
        user_id=user_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shopping list {list_id} not found"
        )

    return {"status": "ok", "deleted": str(list_id)}


def _to_response(shopping_list) -> ShoppingListResponse:
    """Convert ORM ShoppingList to response model."""
    items = [
        ShoppingListItemResponse(
            list_item_id=item.list_item_id,
            list_id=item.list_id,
            ingredient_id=item.ingredient_id,
            ingredient_name=None,  # Could enrich from Neo4j/MongoDB if needed
            needed_qty=float(item.needed_qty),
            unit=item.unit,
            checked=item.checked,
            from_recipe_id=item.from_recipe_id,
            note=item.note
        )
        for item in shopping_list.items
    ]

    return ShoppingListResponse(
        list_id=shopping_list.list_id,
        user_id=shopping_list.user_id,
        plan_id=shopping_list.plan_id,
        created_at=shopping_list.created_at,
        status=shopping_list.status,
        items=items
    )