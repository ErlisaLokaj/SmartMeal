"""Schemas for Save-me-first suggestions (food waste prevention)"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date
from uuid import UUID
from decimal import Decimal


class ExpiringIngredient(BaseModel):
    """Ingredient that's expiring soon"""

    pantry_item_id: UUID
    ingredient_id: UUID
    ingredient_name: str
    quantity: Decimal
    unit: Optional[str]
    best_before: Optional[date]
    days_until_expiry: int
    urgency_level: str  # "critical" (<1 day), "urgent" (1-2 days), "soon" (3+ days)

    model_config = {"from_attributes": True}


class RecipeSuggestion(BaseModel):
    """Recipe suggestion using expiring ingredients"""

    recipe_id: str
    recipe_name: str
    cuisine: Optional[str]
    total_time_minutes: Optional[int]
    servings: int
    uses_expiring_count: int = Field(
        ..., description="Number of expiring ingredients this recipe uses"
    )
    expiring_ingredients_used: List[str] = Field(
        default_factory=list, description="Names of expiring ingredients used"
    )
    match_score: float = Field(
        ..., ge=0, le=100, description="How well recipe matches needs (0-100)"
    )
    urgency_score: float = Field(
        ..., ge=0, le=100, description="How urgent to cook (based on expiry)"
    )
    effort_level: str = Field(
        ..., description="Cooking effort: 'easy', 'medium', 'hard'"
    )
    missing_ingredients_count: int = Field(
        ..., description="Number of ingredients not in pantry"
    )
    can_cook_now: bool = Field(..., description="Whether user has all ingredients")

    model_config = {"from_attributes": True}


class SaveMeFirstResponse(BaseModel):
    """Daily save-me-first suggestions response"""

    user_id: UUID
    generated_at: str = Field(..., description="ISO timestamp when generated")
    expiring_ingredients: List[ExpiringIngredient] = Field(
        default_factory=list, description="Ingredients expiring soon"
    )
    recipe_suggestions: List[RecipeSuggestion] = Field(
        default_factory=list, description="Suggested recipes using expiring items"
    )
    total_expiring: int = Field(..., description="Total number of expiring items")
    critical_count: int = Field(..., description="Items expiring in <1 day")
    urgent_count: int = Field(..., description="Items expiring in 1-2 days")
    tips: List[str] = Field(default_factory=list, description="Waste prevention tips")

    model_config = {"from_attributes": True}


class SaveMeFirstSettings(BaseModel):
    """User settings for save-me-first notifications"""

    user_id: UUID
    enabled: bool = Field(default=True, description="Whether to receive suggestions")
    days_threshold: int = Field(
        default=3, ge=1, le=7, description="Days before expiry to trigger (1-7)"
    )
    max_suggestions: int = Field(
        default=5, ge=1, le=20, description="Max number of recipe suggestions (1-20)"
    )
    notification_time: Optional[str] = Field(
        None, description="Preferred notification time (HH:MM format)"
    )
    include_partial_matches: bool = Field(
        default=True,
        description="Include recipes even if missing some ingredients",
    )

    model_config = {"from_attributes": True}
