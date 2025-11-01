from typing import Optional, Dict, Any
import logging
from neo4j import GraphDatabase
import os

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4jpassword")

_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

logger = logging.getLogger("smartmeal.graph")

_driver = None


def connect(uri: str, user: str, password: str):
    global _driver
    try:
        _driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Connected to Neo4j %s", uri)
    except Exception as exc:  # pragma: no cover - driver optional in tests
        _driver = None
        logger.warning(
            "Could not initialize neo4j driver: %s — falling back to stub", exc
        )


def close():
    global _driver
    try:
        if _driver is not None:
            _driver.close()
            logger.info("Neo4j driver closed")
    except Exception:
        logger.exception("Error closing neo4j driver")
    finally:
        _driver = None


def get_ingredient_meta(ingredient_id: str) -> Dict[str, Any]:
    """Return ingredient metadata from Neo4j.

    Expected return shape (example):
      {"category": "vegetable", "perishability": "perishable", "defaults": {"shelf_life_days": 7}}

    `ingredient_id` is treated as a string (UUID) that maps to a node in Neo4j.
    If the driver is not available or the node is not found, a set of sensible
    defaults is returned.
    """
    # If we have a real driver, query Neo4j
    if _driver is not None:
        try:
            with _driver.session() as session:
                result = session.run(
                    "MATCH (i:Ingredient {id: $id}) RETURN i.category AS category, i.perishability AS perishability, i.shelf_life_days AS shelf_life_days",
                    id=str(ingredient_id),
                )
                rec = result.single()
                if rec:
                    return {
                        "category": rec["category"] or "unknown",
                        "perishability": rec["perishability"] or "non_perishable",
                        "defaults": {
                            "shelf_life_days": (
                                int(rec["shelf_life_days"])
                                if rec["shelf_life_days"] is not None
                                else None
                            )
                        },
                    }
        except Exception:
            logger.exception("Error querying neo4j for ingredient %s", ingredient_id)

    # Fallback stub logic: map some known ingredient ids/names to metadata
    # This is intentionally simple; a production system should rely on Neo4j data.
    lower = str(ingredient_id).lower()
    if "chicken" in lower:
        return {
            "category": "meat",
            "perishability": "perishable",
            "defaults": {"shelf_life_days": 5},
        }
    if "rice" in lower or "quinoa" in lower:
        return {
            "category": "grain",
            "perishability": "non_perishable",
            "defaults": {"shelf_life_days": 365},
        }
    if "milk" in lower or "yogurt" in lower:
        return {
            "category": "dairy",
            "perishability": "perishable",
            "defaults": {"shelf_life_days": 7},
        }

    # generic default
    return {
        "category": "unknown",
        "perishability": "non_perishable",
        "defaults": {"shelf_life_days": 365},
    }


def suggest_substitutes(ingredient_name: str, limit: int = 5):
    """Return a short list of substitute ingredient names for a given ingredient.

    If Neo4j is available this will query substitute relationships; otherwise
    a small hard-coded map is used.
    """
    if _driver is not None:
        try:
            with _driver.session() as session:
                q = (
                    "MATCH (i:Ingredient {name: $name})-[:SUBSTITUTED_BY]->(s:Ingredient) "
                    "RETURN s.name AS name LIMIT $limit"
                )
                rows = session.run(q, name=ingredient_name, limit=limit)
                return [r["name"] for r in rows]
        except Exception:
            logger.exception("Error querying substitutes for %s", ingredient_name)

    # Stub map
    substitutes = {
        "chicken": ["tofu", "tempeh"],
        "rice": ["quinoa"],
        "milk": ["soy milk", "almond milk"],
    }
    for k, v in substitutes.items():
        if k in ingredient_name.lower():
            return v[:limit]
    return []

def get_substitutes_for_recipe(recipe_id: str):
    """
    Returns a list of ingredient substitutions for a specific recipe.
    """
    query = """
    MATCH (r:Recipe {id: $id})-[:CONTAINS]->(i:Ingredient)
    OPTIONAL MATCH (i)-[:SUBSTITUTED_BY]->(s:Ingredient)
    RETURN DISTINCT i.name AS ingredient, collect(DISTINCT s.name) AS substitutes
    """
    with _driver.session() as session:
        result = session.run(query, {"id": recipe_id})
        return {r["ingredient"]: r["substitutes"] for r in result if r["substitutes"]}


def get_disallowed_ingredient_ids(allergy_names):
    """Returns a list of ingredient IDs associated with allergies."""
    query = """
    MATCH (a:Allergy)-[:TRIGGERS]->(i:Ingredient)
    WHERE a.name IN $allergies
    RETURN i.ingredient_id AS id
    """
    with _driver.session() as session:
        result = session.run(query, allergies=allergy_names)
        return [r["id"] for r in result if r.get("id")]