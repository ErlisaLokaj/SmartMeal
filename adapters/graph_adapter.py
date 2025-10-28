"""Neo4j adapter for ingredient metadata and substitution lookups.

This module provides a small wrapper around the neo4j driver. If the
`neo4j` package is not installed, the module falls back to a lightweight
in-memory stub so the application (and tests) can run without a running
Neo4j instance. For production, install `neo4j` and set NEO4J_* env vars.
"""

from typing import Optional, Dict, Any
import logging

logger = logging.getLogger("smartmeal.graph")

_driver = None


def connect(uri: str, user: str, password: str):
    """Initialize a neo4j driver.

    If the driver package is unavailable, this becomes a no-op and the
    other functions will use a fallback behavior.
    """
    global _driver
    try:
        from neo4j import GraphDatabase

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


def suggest_substitutes(ingredient_id: str, limit: int = 5):
    """Return a short list of substitute ingredient ids/names for a given ingredient.

    If Neo4j is available this will query substitute relationships; otherwise
    a small hard-coded map is used.
    """
    if _driver is not None:
        try:
            with _driver.session() as session:
                q = (
                    "MATCH (i:Ingredient {id: $id})-[:SUBSTITUTE]->(s:Ingredient) "
                    "RETURN s.id AS id LIMIT $limit"
                )
                rows = session.run(q, id=str(ingredient_id), limit=limit)
                return [r["id"] for r in rows]
        except Exception:
            logger.exception("Error querying substitutes for %s", ingredient_id)

    # Stub map
    substitutes = {
        "chicken": ["tofu", "tempeh"],
        "rice": ["quinoa"],
        "milk": ["soy milk", "almond milk"],
    }
    for k, v in substitutes.items():
        if k in str(ingredient_id).lower():
            return v[:limit]
    return []
