"""
Domain schemas package - Pydantic models for validation.
"""

from domain.schemas.profile_schemas import (
    UserCreate,
    UserProfileResponse,
    DietaryProfileCreate,
    DietaryProfileResponse,
    AllergyCreate,
    AllergyResponse,
    PreferenceCreate,
    PreferenceResponse,
    ProfileUpdateRequest,
    PantryItemCreate,
    PantryItemCreateRequest,
    PantryUpdateRequest,
    PantryItemResponse,
)
from domain.schemas.waste_schemas import (
    WasteLogCreate,
    WasteLogResponse,
    WasteInsightsResponse,
    WasteByIngredient,
    WasteByCategory,
    WasteTrend,
)
from domain.schemas.cooking_schemas import (
    CookRecipeRequest,
    CookRecipeResponse,
    IngredientShortage,
    NutritionalSummary,
    CookingLogEntry,
    CookingHistoryResponse,
    CookingStatsResponse,
)

__all__ = [
    # Profile schemas
    "UserCreate",
    "UserProfileResponse",
    "DietaryProfileCreate",
    "DietaryProfileResponse",
    "AllergyCreate",
    "AllergyResponse",
    "PreferenceCreate",
    "PreferenceResponse",
    "ProfileUpdateRequest",
    # Pantry schemas
    "PantryItemCreate",
    "PantryItemCreateRequest",
    "PantryUpdateRequest",
    "PantryItemResponse",
    # Waste schemas
    "WasteLogCreate",
    "WasteLogResponse",
    "WasteInsightsResponse",
    "WasteByIngredient",
    "WasteByCategory",
    "WasteTrend",
    # Cooking schemas
    "CookRecipeRequest",
    "CookRecipeResponse",
    "IngredientShortage",
    "NutritionalSummary",
    "CookingLogEntry",
    "CookingHistoryResponse",
    "CookingStatsResponse",
]
