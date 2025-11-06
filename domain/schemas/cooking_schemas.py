"""Schemas for cooking operations and responses"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class IngredientShortage(BaseModel):
    """Details about an ingredient shortage when cooking"""

    ingredient_id: UUID
    ingredient_name: Optional[str] = None
    needed_quantity: Decimal
    available_quantity: Decimal
    deficit_quantity: Decimal
    unit: Optional[str] = None


class NutritionalSummary(BaseModel):
    """Nutritional information per serving"""

    calories_per_serving: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    fiber_g: Optional[float] = None
    sodium_mg: Optional[float] = None


class CookRecipeRequest(BaseModel):
    """Schema for cooking a recipe"""

    user_id: str = Field(..., description="User ID who is cooking")
    recipe_id: str = Field(..., description="Recipe ID to cook")
    servings: int = Field(..., ge=1, le=20, description="Number of servings (1-20)")

    model_config = {"from_attributes": True}


class CookRecipeResponse(BaseModel):
    """Comprehensive response after cooking a recipe"""

    success: bool = Field(..., description="Whether cooking was successful")
    message: str = Field(..., description="Human-readable message")
    recipe_name: str = Field(..., description="Name of the cooked recipe")
    servings: int = Field(..., description="Number of servings cooked")
    pantry_updated: bool = Field(
        ..., description="Whether pantry was successfully updated"
    )
    shortages: List[IngredientShortage] = Field(
        default_factory=list,
        description="List of ingredients that were short in pantry",
    )
    nutritional_summary: Optional[NutritionalSummary] = Field(
        None, description="Nutritional information per serving"
    )
    waste_prevention_tips: List[str] = Field(
        default_factory=list, description="Tips to prevent food waste"
    )
    suggestions: List[str] = Field(
        default_factory=list, description="Personalized suggestions for the user"
    )

    model_config = {"from_attributes": True}


class CookingLogEntry(BaseModel):
    """Single cooking history entry"""

    cook_id: UUID
    recipe_id: str
    recipe_name: Optional[str] = None
    cuisine: Optional[str] = None
    servings: int
    cooked_at: datetime

    model_config = {"from_attributes": True}


class CookingHistoryResponse(BaseModel):
    """Response containing cooking history"""

    total_count: int = Field(..., description="Total number of cooking logs")
    entries: List[CookingLogEntry] = Field(
        default_factory=list, description="List of cooking log entries"
    )
    period_days: int = Field(..., description="Number of days queried")
    favorite_recipes: Optional[List[Dict[str, Any]]] = Field(
        None, description="Most frequently cooked recipes"
    )

    model_config = {"from_attributes": True}


class CookingStatsResponse(BaseModel):
    """Cooking statistics for a user"""

    total_recipes_cooked: int
    total_servings_cooked: int
    unique_recipes: int
    favorite_cuisine: Optional[str] = None
    recent_activity_days: int
    most_cooked_recipe: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}
