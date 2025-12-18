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
from services.pantry_service import PantryService
from app.exceptions import ServiceValidationError, NotFoundError

router = APIRouter(prefix="/pantry", tags=["Pantry"])
logger = logging.getLogger("smartmeal.api.pantry")


@router.get("", response_model=List[PantryItemResponse])
def get_pantry(user_id: UUID = Query(...), db: Session = Depends(get_db_session)):
    """Get all pantry items for a user"""
    items = PantryService.get_pantry(db, user_id)
    return [PantryItemResponse.model_validate(i) for i in items]


@router.put("", response_model=List[PantryItemResponse])
def update_pantry(pantry: PantryUpdateRequest, db: Session = Depends(get_db_session)):
    """Replace all pantry items for a user"""
    items = PantryService.set_pantry(db, pantry.user_id, pantry.items)
    return [PantryItemResponse.model_validate(i) for i in items]


@router.post("", response_model=PantryItemResponse, status_code=status.HTTP_201_CREATED)
def add_pantry_item(
    payload: PantryItemCreateRequest, db: Session = Depends(get_db_session)
):
    """Add a single pantry item for user (provide user_id in request body)."""
    p = PantryService.add_item(db, payload.user_id, payload.item)
    return PantryItemResponse.model_validate(p)


@router.delete("/{pantry_item_id}")
def delete_pantry_item(pantry_item_id: UUID, db: Session = Depends(get_db_session)):
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
    db: Session = Depends(get_db_session),
):
    """
    Update quantity of a specific pantry item.
    """
    updated_item = PantryService.update_quantity(
        db, pantry_item_id, update.quantity_change, update.reason
    )
    if updated_item is None:
        return {"status": "deleted", "reason": "quantity_reached_zero"}
    return PantryItemResponse.model_validate(updated_item)


@router.get("/expiring-soon", response_model=List[PantryItemResponse])
def get_expiring_soon(
    user_id: UUID = Query(..., description="User ID to fetch pantry for"),
    days: int = Query(
        default=3,
        ge=1,
        le=30,
        description="Number of days ahead to check for expiring items",
    ),
    db: Session = Depends(get_db_session),
):
    """
    Get pantry items expiring within the specified number of days.
    """
    items = PantryService.get_expiring_soon(db, user_id, days)
    return [PantryItemResponse.model_validate(i) for i in items]
