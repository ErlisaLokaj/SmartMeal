"""Ingredient service - master ingredient data management."""

from typing import List, Optional
from sqlalchemy.orm import Session
import logging
from uuid import UUID
from datetime import datetime, timedelta

from domain.models.ingredient import Ingredient
from repositories.ingredient_sql_repository import IngredientSQLRepository

logger = logging.getLogger("smartmeal.ingredient")


class IngredientService:
    """Business logic for ingredient master data management."""

    @staticmethod
    def get_or_create_ingredient(db: Session, name: str) -> Ingredient:
        """
        Get existing ingredient by name, or create if it doesn't exist.
        """
        ingredient_repo = IngredientSQLRepository(db)
        ingredient = ingredient_repo.get_or_create(name)
        return ingredient

    @staticmethod
    def get_ingredient_by_id(db: Session, ingredient_id: UUID) -> Optional[Ingredient]:
        """Get ingredient by ID."""
        ingredient_repo = IngredientSQLRepository(db)
        return ingredient_repo.get_by_id(ingredient_id)

    @staticmethod
    def get_ingredient_by_name(db: Session, name: str) -> Optional[Ingredient]:
        """Get ingredient by name (case-insensitive)."""
        ingredient_repo = IngredientSQLRepository(db)
        return ingredient_repo.get_by_name(name)

    @staticmethod
    def bulk_import_from_mongo(db: Session):
        from adapters import mongo_adapter

        logger.info("Starting bulk import from MongoDB")

        # Get MongoDB database
        mongo_db = mongo_adapter._get_db()

        if "ingredient_master" not in mongo_db.list_collection_names():
            logger.error("ingredient_master collection not found")
            return {"error": "ingredient_master not found", "created": 0, "existing": 0}

        ingredients_mongo = list(mongo_db.ingredient_master.find())

        stats = {"created": 0, "existing": 0, "errors": 0}
        ingredient_repo = IngredientSQLRepository(db)

        for ing_doc in ingredients_mongo:
            name = ing_doc.get("_id")

            if not name:
                stats["errors"] += 1
                continue

            ingredient = ingredient_repo.get_or_create(name)

            if ingredient:
                if (
                    datetime.utcnow() - ingredient.created_at.replace(tzinfo=None)
                ) < timedelta(seconds=1):
                    stats["created"] += 1
                else:
                    stats["existing"] += 1

                # Update MongoDB with PostgreSQL UUID
                mongo_db.ingredient_master.update_one(
                    {"_id": name},
                    {"$set": {"ingredient_id": str(ingredient.ingredient_id)}},
                )

        logger.info(f"Bulk import complete: {stats}")
        return stats

    @staticmethod
    def sync_all_recipes_to_master(db: Session):
        """
        Update ALL MongoDB recipes to use ingredient_ids from PostgreSQL master table.
        """
        from adapters import mongo_adapter

        logger.info("Starting recipe sync to master ingredients")

        mongo_db = mongo_adapter._get_db()

        # Get all ingredients from PostgreSQL using repository
        ingredient_repo = IngredientSQLRepository(db)
        ingredients = ingredient_repo.get_all(limit=10000)  # Get all ingredients
        name_to_id = {ing.name: str(ing.ingredient_id) for ing in ingredients}

        logger.info(f"Loaded {len(name_to_id)} ingredients from PostgreSQL")

        updated_recipes = 0
        updated_ingredients = 0

        recipes = mongo_db.recipes.find({}, {"_id": 1, "ingredients": 1})

        for recipe in recipes:
            modified = False

            for ingredient in recipe.get("ingredients", []):
                ing_name = ingredient.get("name", "").lower().strip()

                if ing_name in name_to_id:
                    new_uuid = name_to_id[ing_name]
                    old_uuid = ingredient.get("ingredient_id")

                    if old_uuid != new_uuid:
                        ingredient["ingredient_id"] = new_uuid
                        modified = True
                        updated_ingredients += 1

            if modified:
                mongo_db.recipes.update_one(
                    {"_id": recipe["_id"]},
                    {"$set": {"ingredients": recipe["ingredients"]}},
                )
                updated_recipes += 1

        logger.info(
            f"Recipe sync complete: {updated_recipes} recipes, {updated_ingredients} ingredients"
        )

        return {
            "updated_recipes": updated_recipes,
            "updated_ingredients": updated_ingredients,
        }
