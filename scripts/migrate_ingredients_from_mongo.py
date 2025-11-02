"""
Migration script: Bulk import ingredients from MongoDB to PostgreSQL

This is a one-time migration script that imports all unique ingredients
from the MongoDB ingredient_master collection to the PostgreSQL database.

Safe to run multiple times - won't create duplicates.

Usage:
    python scripts/migrate_ingredients_from_mongo.py
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path to import from project
sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.models import get_db_session, Ingredient
from adapters import mongo_adapter
from datetime import datetime, timedelta
from sqlalchemy import func

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def bulk_import_from_mongo():
    """
    Import all unique ingredients from MongoDB to PostgreSQL.
    """
    logger.info("Starting bulk import from MongoDB")

    # Get MongoDB database
    mongo_db = mongo_adapter._get_db()

    if mongo_db is None:
        logger.error("MongoDB connection failed")
        return {"error": "MongoDB not available", "created": 0, "existing": 0}

    if "ingredient_master" not in mongo_db.list_collection_names():
        logger.error("ingredient_master collection not found")
        return {"error": "ingredient_master not found", "created": 0, "existing": 0}

    ingredients_mongo = list(mongo_db.ingredient_master.find())
    logger.info(f"Found {len(ingredients_mongo)} ingredients in MongoDB")

    stats = {"created": 0, "existing": 0, "errors": 0}

    # Get database session
    with get_db_session() as db:
        for ing_doc in ingredients_mongo:
            name = ing_doc.get("_id")  # Name is in _id field

            if not name:
                stats["errors"] += 1
                continue

            normalized_name = name.lower().strip()

            # Check if ingredient already exists
            existing = (
                db.query(Ingredient)
                .filter(func.lower(Ingredient.name) == normalized_name)
                .first()
            )

            if existing:
                stats["existing"] += 1
                ingredient = existing
            else:
                # Create new ingredient
                ingredient = Ingredient(name=normalized_name)
                db.add(ingredient)
                db.commit()
                db.refresh(ingredient)
                stats["created"] += 1
                logger.info(f"Created ingredient: {normalized_name}")

            # Update MongoDB with PostgreSQL UUID
            mongo_db.ingredient_master.update_one(
                {"_id": name},
                {"$set": {"ingredient_id": str(ingredient.ingredient_id)}},
            )

    logger.info(f"Bulk import complete: {stats}")
    return stats


def sync_all_recipes_to_master():
    """
    Update ALL MongoDB recipes to use ingredient_ids from PostgreSQL master table.
    """
    logger.info("Starting recipe sync to master ingredients")

    mongo_db = mongo_adapter._get_db()

    if mongo_db is None:
        logger.error("MongoDB connection failed")
        return {"error": "MongoDB not available"}

    # Get all ingredients from PostgreSQL
    with get_db_session() as db:
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
                {"_id": recipe["_id"]}, {"$set": {"ingredients": recipe["ingredients"]}}
            )
            updated_recipes += 1

    logger.info(
        f"Recipe sync complete: {updated_recipes} recipes, {updated_ingredients} ingredients"
    )

    return {
        "updated_recipes": updated_recipes,
        "updated_ingredients": updated_ingredients,
    }


if __name__ == "__main__":
    print("=" * 60)
    print("Ingredient Migration Script")
    print("=" * 60)
    print()

    # Step 1: Import ingredients
    print("Step 1: Importing ingredients from MongoDB to PostgreSQL...")
    result1 = bulk_import_from_mongo()
    print(f"Result: {result1}")
    print()

    # Step 2: Sync recipes
    print("Step 2: Syncing recipe ingredient IDs...")
    result2 = sync_all_recipes_to_master()
    print(f"Result: {result2}")
    print()

    print("=" * 60)
    print("Migration complete!")
    print("=" * 60)
