"""Pydantic schemas for shopping list operations."""

from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime


class ShoppingListCreate(BaseModel):
    """Request to create a shopping list from a meal plan."""
    plan_id: UUID
    user_id: UUID


class ShoppingListItemResponse(BaseModel):
    """Individual item in a shopping list."""
    list_item_id: UUID
    list_id: UUID
    ingredient_id: UUID
    ingredient_name: Optional[str]
    needed_qty: float
    unit: Optional[str]
    checked: bool = False
    from_recipe_id: Optional[UUID] = None
    note: Optional[str] = None

    model_config = {"from_attributes": True}


class ShoppingListResponse(BaseModel):
    """Complete shopping list with items."""
    list_id: UUID
    user_id: UUID
    plan_id: Optional[UUID]
    created_at: datetime
    status: Optional[str]
    items: List[ShoppingListItemResponse] = []

    model_config = {"from_attributes": True}


class ShoppingListItemUpdate(BaseModel):
    """Update a shopping list item"""
    checked: Optional[bool] = None
    note: Optional[str] = None