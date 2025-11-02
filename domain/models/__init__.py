"""
Domain models package - SQLAlchemy ORM models.
"""

from domain.models.database import (
    Base,
    engine,
    SessionLocal,
    init_database,
    get_db_session,
)
from domain.models.user import AppUser, DietaryProfile, UserAllergy, UserPreference
from domain.models.pantry import PantryItem, WasteLog
from domain.models.ingredient import Ingredient
from domain.models.meal_plan import (
    MealPlan,
    MealEntry,
    MealEntryRecipeSnapshot,
    ShoppingList,
    ShoppingListItem,
    CookingLog,
)

__all__ = [
    # Database
    "Base",
    "engine",
    "SessionLocal",
    "init_database",
    "get_db_session",
    # User models
    "AppUser",
    "DietaryProfile",
    "UserAllergy",
    "UserPreference",
    # Ingredient models
    "Ingredient",
    # Pantry models
    "PantryItem",
    "WasteLog",
    # Meal plan models
    "MealPlan",
    "MealEntry",
    "MealEntryRecipeSnapshot",
    "ShoppingList",
    "ShoppingListItem",
    "CookingLog",
]
