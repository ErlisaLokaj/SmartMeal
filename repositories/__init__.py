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
from repositories.ingredient_repository import IngredientRepository
from repositories.ingredient_sql_repository import IngredientSQLRepository
from repositories.shopping_repository import (
    ShoppingListRepository,
    ShoppingListItemRepository,
)
from repositories.meal_plan_repository import MealPlanRepository, MealEntryRepository
from repositories.cooking_log_repository import CookingLogRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "DietaryProfileRepository",
    "AllergyRepository",
    "PreferenceRepository",
    "PantryRepository",
    "WasteRepository",
    "RecipeRepository",
    "IngredientRepository",
    "IngredientSQLRepository",
    "ShoppingListRepository",
    "ShoppingListItemRepository",
    "MealPlanRepository",
    "MealEntryRepository",
    "CookingLogRepository",
]
