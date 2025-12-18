"""
Sync Neo4j Ingredient nodes with MongoDB ingredient_master UUIDs.

This ensures every Ingredient node in Neo4j has a matching ingredient_id
from the master ingredient catalog in MongoDB.
"""

from pymongo import MongoClient
from neo4j import GraphDatabase
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


MONGO_URI = os.getenv("MONGO_URI", "mongodb://smartmeal-mongo:27017")
MONGO_DB = os.getenv("MONGO_DB", "smartmeal")

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://smartmeal-neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4jpassword")



def main():
    logging.info("Connecting to MongoDB...")
    mongo = MongoClient(MONGO_URI)
    db = mongo[MONGO_DB]

    ingredients = list(db.ingredient_master.find({}, {"_id": 1, "ingredient_id": 1}))
    logging.info(f"Loaded {len(ingredients)} ingredients from MongoDB master")

    logging.info("Connecting to Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    created, updated = 0, 0

    with driver.session() as session:
        for doc in ingredients:
            name = doc.get("_id", "").strip().lower()
            uuid = doc.get("ingredient_id")

            if not name or not uuid:
                logging.warning(f"Skipping ingredient without UUID: {name}")
                continue

            result = session.run(
                """
                MATCH (i:Ingredient {name: $name})
                SET i.ingredient_id = $uuid
                RETURN count(i) AS updated
                """,
                name=name,
                uuid=uuid,
            ).single()

            if result["updated"] == 0:
                session.run(
                    """
                    MERGE (i:Ingredient {name: $name})
                    SET i.ingredient_id = $uuid
                    """,
                    name=name,
                    uuid=uuid,
                )
                created += 1
            else:
                updated += 1

    logging.info(f"Sync complete: updated={updated}, created={created}")
    driver.close()
    mongo.close()


if __name__ == "__main__":
    main()
