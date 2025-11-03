#!/usr/bin/env python3
"""
Initialize all databases (PostgreSQL, MongoDB, Neo4j)
Creates schemas, tables, collections, and optionally seeds data
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("init_databases")


def init_postgresql():
    """Initialize PostgreSQL tables"""
    logger.info("=" * 60)
    logger.info("Initializing PostgreSQL...")
    logger.info("=" * 60)

    try:
        from domain.models.database import init_database

        init_database()
        logger.info("✓ PostgreSQL tables created successfully!")

        # Verify tables were created
        from domain.models.database import engine
        from sqlalchemy import inspect

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"✓ Created {len(tables)} tables: {', '.join(tables)}")

        return True
    except Exception as e:
        logger.error(f"✗ Failed to initialize PostgreSQL: {e}")
        import traceback

        traceback.print_exc()
        return False


def init_mongodb():
    """Initialize MongoDB collections and indexes"""
    logger.info("=" * 60)
    logger.info("Initializing MongoDB...")
    logger.info("=" * 60)

    try:
        import adapters.mongo_adapter as mongo_adapter
        from app.config import MONGO_URI, MONGO_DB

        # Connect to MongoDB
        mongo_adapter.connect(MONGO_URI, MONGO_DB)

        # Get database instance
        db = mongo_adapter._db
        if db is None:
            raise Exception("Failed to connect to MongoDB")

        # Recipes collection
        if "recipes" not in db.list_collection_names():
            db.create_collection("recipes")
            logger.info("✓ Created 'recipes' collection")

        # Create indexes for better query performance
        db.recipes.create_index("recipe_id", unique=True)
        db.recipes.create_index("name")
        db.recipes.create_index("cuisine")
        db.recipes.create_index("tags")
        logger.info("✓ Created indexes on 'recipes' collection")

        # Check if we need to seed recipes
        recipe_count = db.recipes.count_documents({})
        logger.info(f"✓ MongoDB initialized with {recipe_count} recipes")

        if recipe_count == 0:
            logger.info("→ No recipes found. You can import recipes using:")
            logger.info("  python data/import_recipes.py")

        return True
    except Exception as e:
        logger.error(f"✗ Failed to initialize MongoDB: {e}")
        import traceback

        traceback.print_exc()
        return False


def init_neo4j():
    """Initialize Neo4j constraints and indexes"""
    logger.info("=" * 60)
    logger.info("Initializing Neo4j...")
    logger.info("=" * 60)

    try:
        import adapters.graph_adapter as graph_adapter
        from app.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

        # Connect to Neo4j
        graph_adapter.connect(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

        # Get driver instance
        driver = graph_adapter._driver
        if driver is None:
            raise Exception("Failed to connect to Neo4j")

        # Create constraints and indexes
        with driver.session() as session:
            # Create uniqueness constraint on Ingredient name
            try:
                session.run(
                    "CREATE CONSTRAINT ingredient_name_unique IF NOT EXISTS "
                    "FOR (i:Ingredient) REQUIRE i.name IS UNIQUE"
                )
                logger.info("✓ Created uniqueness constraint on Ingredient.name")
            except Exception as e:
                logger.warning(f"Constraint may already exist: {e}")

            # Create index on category for faster queries
            try:
                session.run(
                    "CREATE INDEX ingredient_category_idx IF NOT EXISTS "
                    "FOR (i:Ingredient) ON (i.category)"
                )
                logger.info("✓ Created index on Ingredient.category")
            except Exception as e:
                logger.warning(f"Index may already exist: {e}")

            # Count ingredients
            result = session.run("MATCH (i:Ingredient) RETURN count(i) as count")
            ingredient_count = result.single()["count"]

            # Count substitutions
            result = session.run(
                "MATCH ()-[r:CAN_SUBSTITUTE]->() RETURN count(r) as count"
            )
            sub_count = result.single()["count"]

            logger.info(
                f"✓ Neo4j initialized with {ingredient_count} ingredients and {sub_count} substitutions"
            )

            if ingredient_count == 0:
                logger.info("→ No ingredients found. Running auto-seed...")
                import subprocess

                result = subprocess.run(
                    [
                        sys.executable,
                        "scripts/seed_neo4j.py",
                        "--file",
                        "data/substitution_pairs.json",
                        "--uri",
                        NEO4J_URI,
                        "--user",
                        NEO4J_USER,
                        "--password",
                        NEO4J_PASSWORD,
                    ],
                    capture_output=True,
                    text=True,
                )

                if result.returncode == 0:
                    logger.info("✓ Neo4j seeded successfully!")
                else:
                    logger.error(f"✗ Seeding failed: {result.stderr}")

        return True
    except Exception as e:
        logger.error(f"✗ Failed to initialize Neo4j: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all database initializations"""
    logger.info("=" * 60)
    logger.info("SmartMeal Database Initialization")
    logger.info("=" * 60)

    results = {
        "PostgreSQL": init_postgresql(),
        "MongoDB": init_mongodb(),
        "Neo4j": init_neo4j(),
    }

    logger.info("=" * 60)
    logger.info("Initialization Summary")
    logger.info("=" * 60)

    for db_name, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        logger.info(f"{db_name}: {status}")

    all_success = all(results.values())

    if all_success:
        logger.info("=" * 60)
        logger.info("✓ All databases initialized successfully!")
        logger.info("=" * 60)
        return 0
    else:
        logger.error("=" * 60)
        logger.error("✗ Some databases failed to initialize")
        logger.error("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
