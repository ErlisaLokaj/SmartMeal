"""Ingredient service - master ingredient data management."""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
import logging
from uuid import UUID

from core.database.models import Ingredient

logger = logging.getLogger("smartmeal.ingredient")


class IngredientService:
    """Business logic for ingredient master data management."""

    @staticmethod
    def get_or_create_ingredient(db: Session, name: str) -> Ingredient:
        """
        Get existing ingredient by name, or create if it doesn't exist.

        This is the key method - it ensures we always use the same UUID
        for the same ingredient name.
        """
        normalized_name = name.lower().strip()

        # Try to find existing
        ingredient = db.query(Ingredient).filter(
            func.lower(Ingredient.name) == normalized_name
        ).first()

        if ingredient:
            return ingredient

        # Create new if not found
        ingredient = Ingredient(name=normalized_name)
        db.add(ingredient)

        try:
            db.commit()
            db.refresh(ingredient)
            logger.info(f"ingredient_created name={normalized_name} id={ingredient.ingredient_id}")
            return ingredient
        except IntegrityError:
            # Race condition - another request created it
            db.rollback()
            return db.query(Ingredient).filter(
                func.lower(Ingredient.name) == normalized_name
            ).first()

    @staticmethod
    def get_ingredient_by_id(db: Session, ingredient_id: UUID) -> Optional[Ingredient]:
        """Get ingredient by ID."""
        return db.query(Ingredient).filter(
            Ingredient.ingredient_id == ingredient_id
        ).first()

    @staticmethod
    def get_ingredient_by_name(db: Session, name: str) -> Optional[Ingredient]:
        """Get ingredient by name (case-insensitive)."""
        normalized_name = name.lower().strip()
        return db.query(Ingredient).filter(
            func.lower(Ingredient.name) == normalized_name
        ).first()

    @staticmethod
    def bulk_import_from_mongo(db: Session):
        """
        Import all unique ingredients from MongoDB to PostgreSQL.

        This is a one-time migration that can be triggered via API.
        Safe to run multiple times - won't create duplicates.
        """
        from adapters import mongo_adapter

        logger.info("Starting bulk import from MongoDB")

        # Get MongoDB database
        mongo_db = mongo_adapter._get_db()

        if "ingredient_master" not in mongo_db.list_collection_names():
            logger.error("ingredient_master collection not found")
            return {"error": "ingredient_master not found", "created": 0, "existing": 0}

        ingredients_mongo = list(mongo_db.ingredient_master.find())

        stats = {"created": 0, "existing": 0, "errors": 0}

        for ing_doc in ingredients_mongo:
            name = ing_doc.get("_id")  # Name is in _id field

            if not name:
                stats["errors"] += 1
                continue

            # Use get_or_create to avoid duplicates
            ingredient = IngredientService.get_or_create_ingredient(db, name)

            if ingredient:
                # Check if this is new or existing
                existing_count = db.query(Ingredient).filter(
                    Ingredient.name == name.lower().strip()
                ).count()

                if existing_count == 1:
                    # Check creation time to see if it was just created
                    from datetime import datetime, timedelta
                    if (datetime.utcnow() - ingredient.created_at.replace(tzinfo=None)) < timedelta(seconds=1):
                        stats["created"] += 1
                    else:
                        stats["existing"] += 1

                # Update MongoDB with PostgreSQL UUID
                mongo_db.ingredient_master.update_one(
                    {"_id": name},
                    {"$set": {"ingredient_id": str(ingredient.ingredient_id)}}
                )

        logger.info(f"Bulk import complete: {stats}")
        return stats

    @staticmethod
    def sync_all_recipes_to_master(db: Session):
        """
        Update ALL MongoDB recipes to use ingredient_ids from PostgreSQL master table.

        This fixes the inconsistent UUID problem.
        """
        from adapters import mongo_adapter

        logger.info("Starting recipe sync to master ingredients")

        mongo_db = mongo_adapter._get_db()

        # Get all ingredients from PostgreSQL
        ingredients = db.query(Ingredient).all()
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
                    {"$set": {"ingredients": recipe["ingredients"]}}
                )
                updated_recipes += 1

        logger.info(f"Recipe sync complete: {updated_recipes} recipes, {updated_ingredients} ingredients")

        return {
            "updated_recipes": updated_recipes,
            "updated_ingredients": updated_ingredients
        }