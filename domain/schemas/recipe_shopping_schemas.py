"""Schemas for recipe-based shopping list generation"""

from pydantic import BaseModel, Field
from typing import List
from uuid import UUID
from decimal import Decimal


class RecipeShoppingItem(BaseModel):
    """Single item needed for a recipe"""

    ingredient_id: UUID
    ingredient_name: str
    needed_quantity: Decimal
    available_quantity: Decimal
    to_buy_quantity: Decimal
    unit: str

    model_config = {"from_attributes": True}


class RecipeShoppingListRequest(BaseModel):
    """Request to generate shopping list for a recipe"""

    user_id: str = Field(..., description="User ID")
    recipe_id: str = Field(..., description="Recipe ID")
    servings: int = Field(..., ge=1, le=20, description="Number of servings (1-20)")

    model_config = {"from_attributes": True}


class RecipeShoppingListResponse(BaseModel):
    """Response with shopping list for a recipe"""

    recipe_id: str
    recipe_name: str
    servings: int
    missing_items: List[RecipeShoppingItem] = Field(
        default_factory=list, description="Items needed from store"
    )
    has_all_ingredients: bool = Field(
        ..., description="Whether user has everything in pantry"
    )
    total_items_needed: int = Field(..., description="Total number of items to buy")
    can_cook_now: bool = Field(..., description="Whether user can cook immediately")

    model_config = {"from_attributes": True}
