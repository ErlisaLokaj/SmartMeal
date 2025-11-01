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
]
