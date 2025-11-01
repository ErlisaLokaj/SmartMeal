"""
Repositories package - Data access layer.
"""

from repositories.base import BaseRepository
from repositories.user_repository import (
    UserRepository,
    DietaryProfileRepository,
    AllergyRepository,
    PreferenceRepository,
)
from repositories.pantry_repository import PantryRepository
from repositories.waste_repository import WasteRepository
from repositories.recipe_repository import RecipeRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "DietaryProfileRepository",
    "AllergyRepository",
    "PreferenceRepository",
    "PantryRepository",
    "WasteRepository",
    "RecipeRepository",
]
