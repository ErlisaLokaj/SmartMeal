#!/usr/bin/env python3
"""
Load recipes from recipes_structured.json into MongoDB.
This script populates the MongoDB recipes collection with structured recipe data.

Usage:
    python scripts/load_recipes_to_mongo.py          # Interactive mode
    python scripts/load_recipes_to_mongo.py --auto   # Auto mode (skip if exists)
"""

import sys
import json
import logging
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("load_recipes")


def load_recipes_to_mongodb(auto_mode=False):
    """Load structured recipes into MongoDB."""
    try:
        import adapters.mongo_adapter as mongo_adapter
        from app.config import MONGO_URI, MONGO_DB

        # Connect to MongoDB
        logger.info("Connecting to MongoDB...")
        mongo_adapter.connect(MONGO_URI, MONGO_DB)

        db = mongo_adapter._db
        if db is None:
            raise Exception("Failed to connect to MongoDB")

        logger.info("✓ Connected to MongoDB")

        # Load recipes from JSON file
        recipes_file = Path(__file__).parent.parent / "data" / "recipes_structured.json"

        if not recipes_file.exists():
            logger.error(f"✗ Recipe file not found: {recipes_file}")
            logger.info(
                "Please ensure recipes_structured.json exists in the data/ directory"
            )
            return False

        logger.info(f"Loading recipes from {recipes_file}...")
        with open(recipes_file, "r", encoding="utf-8") as f:
            recipes = json.load(f)

        logger.info(f"✓ Loaded {len(recipes)} recipes from file")

        # Check if recipes already exist
        existing_count = db.recipes.count_documents({})
        if existing_count > 0:
            if auto_mode:
                logger.info(
                    f"✓ MongoDB already contains {existing_count} recipes (auto mode: skipping)"
                )
                return True
            else:
                logger.warning(f"⚠ MongoDB already contains {existing_count} recipes")
                response = input(
                    "Do you want to (1) skip, (2) replace all, or (3) add new? [1/2/3]: "
                )

                if response == "2":
                    logger.info("Dropping existing recipes collection...")
                    db.recipes.drop()
                    db.create_collection("recipes")
                    logger.info("✓ Dropped existing recipes")
                elif response == "1":
                    logger.info("Skipping recipe import")
                    return True
                # Option 3 will just insert new recipes

        # Insert recipes into MongoDB
        logger.info("Inserting recipes into MongoDB...")

        # Insert in batches for better performance
        batch_size = 100
        inserted_count = 0
        skipped_count = 0

        for i in range(0, len(recipes), batch_size):
            batch = recipes[i : i + batch_size]

            try:
                result = db.recipes.insert_many(batch, ordered=False)
                inserted_count += len(result.inserted_ids)
                logger.info(
                    f"✓ Inserted batch {i//batch_size + 1}: {len(result.inserted_ids)} recipes"
                )
            except Exception as e:
                # Some recipes might already exist (duplicate _id)
                if "duplicate key error" in str(e).lower():
                    # Try inserting one by one to count successes
                    for recipe in batch:
                        try:
                            db.recipes.insert_one(recipe)
                            inserted_count += 1
                        except:
                            skipped_count += 1
                else:
                    logger.error(f"Error inserting batch: {e}")
                    continue

        # Create indexes for better query performance
        logger.info("Creating indexes...")
        # Note: _id is already unique by default, no need to create index
        db.recipes.create_index("title")
        db.recipes.create_index("cuisine_id")
        db.recipes.create_index("tags")
        db.recipes.create_index("slug")
        logger.info("✓ Created indexes")

        # Summary
        final_count = db.recipes.count_documents({})
        logger.info("=" * 60)
        logger.info("RECIPE IMPORT SUMMARY")
        logger.info("=" * 60)
        logger.info(f"✓ Total recipes in file: {len(recipes)}")
        logger.info(f"✓ Successfully inserted: {inserted_count}")
        if skipped_count > 0:
            logger.info(f"⚠ Skipped (duplicates): {skipped_count}")
        logger.info(f"✓ Total recipes in MongoDB: {final_count}")
        logger.info("=" * 60)

        # Show sample recipe
        if final_count > 0:
            sample = db.recipes.find_one()
            logger.info("\nSample recipe:")
            logger.info(f"  Title: {sample.get('title', 'N/A')}")
            logger.info(f"  Cuisine: {sample.get('cuisine_id', 'N/A')}")
            logger.info(f"  Tags: {sample.get('tags', [])}")
            logger.info(f"  Ingredients: {len(sample.get('ingredients', []))}")
            logger.info(f"  Steps: {len(sample.get('steps', []))}")

        return True

    except Exception as e:
        logger.error(f"✗ Failed to load recipes: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Load recipes from recipes_structured.json into MongoDB"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto mode: skip if recipes already exist (for container initialization)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("SMARTMEAL RECIPE LOADER")
    if args.auto:
        logger.info("Mode: AUTO (non-interactive)")
    logger.info("=" * 60)

    success = load_recipes_to_mongodb(auto_mode=args.auto)

    if success:
        logger.info("\n✓ Recipe loading completed successfully!")
        sys.exit(0)
    else:
        logger.error("\n✗ Recipe loading failed!")
        sys.exit(1)
