#!/usr/bin/env python3
"""
Create ingredient_master collection from recipes.
This script extracts all unique ingredients from the recipes collection
and populates the ingredient_master collection.
"""

import logging
import os
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("create_ingredient_master")

# --- CONFIG ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://smartmeal-mongo:27017")
MONGO_DB = os.getenv("MONGO_DB", "smartmeal")
# --------------


def main():
    logger.info("Connecting to MongoDB...")
    try:
        client = MongoClient(MONGO_URI)
        db = client[MONGO_DB]

        # Check connection
        client.admin.command("ping")
        logger.info("Connected to MongoDB")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return

    if "recipes" not in db.list_collection_names():
        logger.error("recipes collection not found! Cannot create ingredient_master.")
        return

    recipe_count = db.recipes.count_documents({})
    logger.info(f"Found {recipe_count} recipes in database")

    logger.info("Extracting unique ingredients from recipes...")

    # Pipeline to extract all ingredient names
    pipeline = [
        {"$unwind": "$ingredients"},
        {"$group": {"_id": "$ingredients.name"}},
        {"$project": {"_id": 1}},  # _id is the ingredient name
    ]

    unique_ingredients = list(db.recipes.aggregate(pipeline))
    logger.info(f"Found {len(unique_ingredients)} unique ingredients")

    if not unique_ingredients:
        logger.warning("No ingredients found in recipes.")
        return

    # Prepare operations for bulk write
    # We use update_one with upsert=True to avoid duplicates and preserve existing data
    from pymongo import UpdateOne

    operations = []
    for doc in unique_ingredients:
        name = doc["_id"]
        if name:
            # Clean the name
            name = name.strip().lower()
            operations.append(
                UpdateOne({"_id": name}, {"$set": {"_id": name}}, upsert=True)
            )

    if operations:
        logger.info(f"Writing {len(operations)} ingredients to ingredient_master...")
        result = db.ingredient_master.bulk_write(operations)
        logger.info(f"Bulk write result: {result.bulk_api_result}")

        # Create index on _id (default) and maybe others if needed
        logger.info("ingredient_master populated successfully")
    else:
        logger.info("No operations to perform")

    client.close()


if __name__ == "__main__":
    main()
