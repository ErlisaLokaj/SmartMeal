"""Pantry management routes"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging
from uuid import UUID
from typing import List

from domain.models import get_db_session
from domain.schemas.profile_schemas import (
    PantryItemResponse,
    PantryItemCreate,
    PantryItemCreateRequest,
    PantryUpdateRequest,
    PantryItemQuantityUpdate,
)
from services import PantryService
from core.exceptions import ServiceValidationError, NotFoundError

router = APIRouter(prefix="/pantry", tags=["Pantry"])
logger = logging.getLogger("smartmeal.api.pantry")


def get_db():
    """Database session dependency"""
    yield from get_db_session()


@router.get("", response_model=List[PantryItemResponse])
def get_pantry(user_id: UUID = Query(...), db: Session = Depends(get_db)):
    """Get all pantry items for a user"""
    items = PantryService.get_pantry(db, user_id)
    return [PantryItemResponse.model_validate(i) for i in items]


@router.put("", response_model=List[PantryItemResponse])
def update_pantry(pantry: PantryUpdateRequest, db: Session = Depends(get_db)):
    """Replace all pantry items for a user"""
    try:
        items = PantryService.set_pantry(db, pantry.user_id, pantry.items)
        return [PantryItemResponse.model_validate(i) for i in items]
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error updating pantry: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("", response_model=PantryItemResponse, status_code=status.HTTP_201_CREATED)
def add_pantry_item(payload: PantryItemCreateRequest, db: Session = Depends(get_db)):
    """Add a single pantry item for user (provide user_id in request body)."""
    try:
        p = PantryService.add_item(db, payload.user_id, payload.item)
        return PantryItemResponse.model_validate(p)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error adding pantry item: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/{pantry_item_id}")
def delete_pantry_item(pantry_item_id: UUID, db: Session = Depends(get_db)):
    """Delete a specific pantry item"""
    success = PantryService.remove_item(db, pantry_item_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pantry item {pantry_item_id} not found",
        )
    return {"status": "ok", "removed": str(pantry_item_id)}


@router.patch("/{pantry_item_id}", response_model=PantryItemResponse)
def update_pantry_item_quantity(
    pantry_item_id: UUID,
    update: PantryItemQuantityUpdate,
    db: Session = Depends(get_db),
):
    """
    Update quantity of a specific pantry item.

    Use this for:
    - Consuming ingredients during cooking (negative quantity_change)
    - Adding more of the same batch (positive quantity_change)
    - Adjusting quantities found in pantry

    If quantity reaches 0, the item is automatically deleted.

    Examples:
    - Consumed 500ml milk: {"quantity_change": -0.5, "reason": "cooking"}
    - Found extra can: {"quantity_change": 1, "reason": "found_more"}
    """
    try:
        updated_item = PantryService.update_quantity(
            db, pantry_item_id, update.quantity_change, update.reason
        )
        if updated_item is None:
            # Item was auto-deleted because quantity reached 0
            return {"status": "deleted", "reason": "quantity_reached_zero"}
        return PantryItemResponse.model_validate(updated_item)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error updating pantry quantity: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/expiring-soon", response_model=List[PantryItemResponse])
def get_expiring_soon(
    user_id: UUID = Query(..., description="User ID to fetch pantry for"),
    days: int = Query(
        default=3,
        ge=1,
        le=30,
        description="Number of days ahead to check for expiring items",
    ),
    db: Session = Depends(get_db),
):
    """
    Get pantry items expiring within the specified number of days.

    This helps users:
    - Prioritize which ingredients to use first (FIFO/FEFO)
    - Prevent food waste by cooking expiring items
    - Plan meals based on what needs to be used soon

    Returns items ordered by expiry date (oldest first).
    Items without expiry dates are excluded.

    Examples:
    - GET /pantry/expiring-soon?user_id={id}&days=3 - Items expiring in next 3 days
    - GET /pantry/expiring-soon?user_id={id}&days=7 - Items expiring in next week
    """
    items = PantryService.get_expiring_soon(db, user_id, days)
    return [PantryItemResponse.model_validate(i) for i in items]
