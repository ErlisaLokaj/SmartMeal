#!/usr/bin/env python3
"""
Verification script to check if ingredients are properly set up across all databases.

Usage:
    python scripts/verify_ingredient_setup.py
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("verify_ingredient_setup")


def verify_mongodb():
    """Check MongoDB ingredient_master collection."""
    try:
        import adapters.mongo_adapter as mongo_adapter
        from app.config import MONGO_URI, MONGO_DB

        mongo_adapter.connect(MONGO_URI, MONGO_DB)
        db = mongo_adapter._db

        if db is None:
            logger.error("✗ MongoDB connection failed")
            return False

        if "ingredient_master" not in db.list_collection_names():
            logger.error("✗ ingredient_master collection not found")
            return False

        count = db.ingredient_master.count_documents({})
        logger.info(f"✓ MongoDB ingredient_master: {count} ingredients")
        return count > 0

    except Exception as e:
        logger.error(f"✗ MongoDB verification failed: {e}")
        return False


def verify_postgresql():
    """Check PostgreSQL ingredients table."""
    try:
        from domain.models import get_db_session, Ingredient

        with get_db_session() as db:
            count = db.query(Ingredient).count()
            logger.info(f"✓ PostgreSQL ingredients table: {count} ingredients")
            return count > 0

    except Exception as e:
        logger.error(f"✗ PostgreSQL verification failed: {e}")
        return False


def verify_neo4j():
    """Check Neo4j Ingredient nodes."""
    try:
        import adapters.graph_adapter as graph_adapter
        from app.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

        graph_adapter.connect(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        driver = graph_adapter._driver

        if driver is None:
            logger.error("✗ Neo4j connection failed")
            return False

        with driver.session() as session:
            # Count ingredients with ingredient_id
            result = session.run(
                """
                MATCH (i:Ingredient)
                WHERE i.ingredient_id IS NOT NULL
                RETURN count(i) as count
                """
            )
            count = result.single()["count"]
            logger.info(f"✓ Neo4j Ingredient nodes with UUID: {count} ingredients")
            return count > 0

    except Exception as e:
        logger.error(f"✗ Neo4j verification failed: {e}")
        return False


def main():
    logger.info("=" * 60)
    logger.info("INGREDIENT SETUP VERIFICATION")
    logger.info("=" * 60)

    results = {
        "MongoDB": verify_mongodb(),
        "PostgreSQL": verify_postgresql(),
        "Neo4j": verify_neo4j(),
    }

    logger.info("=" * 60)
    logger.info("VERIFICATION SUMMARY")
    logger.info("=" * 60)

    for db_name, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        logger.info(f"{db_name}: {status}")

    all_success = all(results.values())

    if all_success:
        logger.info("=" * 60)
        logger.info("✓ All ingredient setups verified successfully!")
        logger.info("=" * 60)
        return 0
    else:
        logger.error("=" * 60)
        logger.error("✗ Some ingredient setups are incomplete")
        logger.error("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
