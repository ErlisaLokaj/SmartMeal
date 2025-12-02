#!/usr/bin/env python3
"""
Create ingredient_master collection from recipes in MongoDB.

This script extracts all unique ingredients from the recipes collection
and creates/updates the ingredient_master collection with their UUIDs and names.

Usage:
    python scripts/create_ingredient_master.py
"""

import sys
import logging
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("create_ingredient_master")


def create_ingredient_master():
    """
    Extract unique ingredients from recipes and create ingredient_master collection.
    """
    try:
        import adapters.mongo_adapter as mongo_adapter
        from app.config import MONGO_URI, MONGO_DB

        logger.info("Connecting to MongoDB...")
        mongo_adapter.connect(MONGO_URI, MONGO_DB)

        db = mongo_adapter._db
        if db is None:
            raise Exception("Failed to connect to MongoDB")

        logger.info("✓ Connected to MongoDB")

        # Check if recipes collection exists
        if "recipes" not in db.list_collection_names():
            logger.error("✗ Recipes collection not found")
            logger.info("  Please load recipes first using: python scripts/load_recipes_to_mongo.py")
            return False

        recipe_count = db.recipes.count_documents({})
        logger.info(f"Found {recipe_count} recipes in MongoDB")

        if recipe_count == 0:
            logger.error("✗ No recipes found in MongoDB")
            logger.info("  Please load recipes first using: python scripts/load_recipes_to_mongo.py")
            return False

        # Extract unique ingredients from all recipes
        logger.info("Extracting ingredients from recipes...")
        
        # Dictionary to store ingredient_id -> name mapping
        # Use the first occurrence of each ingredient_id
        ingredients_map = {}
        
        recipes = db.recipes.find({}, {"ingredients": 1})
        
        for recipe in recipes:
            for ingredient in recipe.get("ingredients", []):
                ing_id = ingredient.get("ingredient_id")
                ing_name = ingredient.get("name", "").lower().strip()
                
                if ing_id and ing_name:
                    # Only add if we haven't seen this ingredient_id before
                    if ing_id not in ingredients_map:
                        ingredients_map[ing_id] = ing_name

        logger.info(f"✓ Found {len(ingredients_map)} unique ingredients")

        # Create or update ingredient_master collection
        existing_count = 0
        if "ingredient_master" in db.list_collection_names():
            existing_count = db.ingredient_master.count_documents({})
            logger.info(f"Found existing ingredient_master collection with {existing_count} ingredients")

        # Insert/update ingredients in ingredient_master
        created = 0
        updated = 0
        
        for ing_id, ing_name in ingredients_map.items():
            # Use name as _id and store ingredient_id as a field
            result = db.ingredient_master.update_one(
                {"_id": ing_name},
                {"$set": {"ingredient_id": ing_id}},
                upsert=True
            )
            
            if result.upserted_id:
                created += 1
            elif result.modified_count > 0:
                updated += 1

        # Summary
        final_count = db.ingredient_master.count_documents({})
        logger.info("=" * 60)
        logger.info("INGREDIENT MASTER CREATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"✓ Unique ingredients extracted: {len(ingredients_map)}")
        logger.info(f"✓ New ingredients created: {created}")
        logger.info(f"✓ Existing ingredients updated: {updated}")
        logger.info(f"✓ Total ingredients in master: {final_count}")
        logger.info("=" * 60)

        # Show sample ingredients
        if final_count > 0:
            logger.info("\nSample ingredients:")
            samples = db.ingredient_master.find().limit(5)
            for sample in samples:
                logger.info(f"  {sample.get('_id')} -> {sample.get('ingredient_id')}")

        return True

    except Exception as e:
        logger.error(f"✗ Failed to create ingredient_master: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("CREATE INGREDIENT MASTER COLLECTION")
    logger.info("=" * 60)

    success = create_ingredient_master()

    if success:
        logger.info("\n✓ Ingredient master collection created successfully!")
        sys.exit(0)
    else:
        logger.error("\n✗ Failed to create ingredient master collection!")
        sys.exit(1)
