from typing import Optional, Dict, Any
import logging
from neo4j import GraphDatabase

logger = logging.getLogger("smartmeal.graph")

_driver = None


def connect(uri: str, user: str, password: str):
    """Initialize a neo4j driver.

    If the driver package is unavailable, this becomes a no-op and the
    other functions will use a fallback behavior.
    """
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
    """
    Return ingredient metadata from Neo4j.

    Expected return shape:
      {
        "name": "Chicken",
        "category": "meat", 
        "perishability": "perishable",
        "proc_id": "some_id",
        "defaults": {"shelf_life_days": 7}
      }

    Args:
        ingredient_id: Ingredient ID (UUID as string, proc_id, or name)

    Returns:
        Dict with ingredient metadata

    Raises:
        RuntimeError: If Neo4j driver is not available
        ValueError: If ingredient not found in Neo4j
    """
    if _driver is None:
        raise RuntimeError(
            "Neo4j driver not initialized. Cannot fetch ingredient metadata. "
            "Ensure Neo4j connection is configured."
        )
    
    try:
        with _driver.session() as session:
            # Search by common identifier properties: id (canonical), proc_id (from processed data), or name
            q = """
            MATCH (i:Ingredient) 
            WHERE i.id = $id OR i.proc_id = $id OR i.name = $id 
            RETURN i.id AS id,
                   i.proc_id AS proc_id,
                   i.name AS name,
                   i.category AS category, 
                   i.perishability AS perishability, 
                   i.shelf_life_days AS shelf_life_days
            """
            result = session.run(q, id=str(ingredient_id))
            rec = result.single()
            
            if rec:
                return {
                    "id": rec["id"],
                    "name": rec["name"] or f"Ingredient-{ingredient_id}",
                    "category": rec["category"] or "unknown",
                    "perishability": rec["perishability"] or "non_perishable",
                    "proc_id": rec["proc_id"],
                    "defaults": {
                        "shelf_life_days": (
                            int(rec["shelf_life_days"]) if rec["shelf_life_days"] is not None else None
                        )
                    },
                }
            else:
                raise ValueError(
                    f"Ingredient '{ingredient_id}' not found in Neo4j database. "
                    "Please ensure the ingredient exists."
                )
    except ValueError:
        # Re-raise ValueError as is
        raise
    except Exception as e:
        logger.exception(f"Error querying Neo4j for ingredient {ingredient_id}")
        raise RuntimeError(
            f"Failed to query Neo4j for ingredient '{ingredient_id}': {str(e)}"
        ) from e


def get_ingredients_batch(ingredient_ids: list) -> Dict[str, Dict[str, Any]]:
    """
    Batch fetch ingredient metadata for multiple ingredients.
    
    This avoids N+1 query problems when processing multiple ingredients.
    
    Args:
        ingredient_ids: List of ingredient IDs (as strings or UUIDs)
    
    Returns:
        Dict mapping ingredient_id to metadata dict
        
    Raises:
        RuntimeError: If Neo4j driver is not available
        ValueError: If any requested ingredients are not found in Neo4j
    """
    if not ingredient_ids:
        return {}
    
    if _driver is None:
        raise RuntimeError(
            "Neo4j driver not initialized. Cannot fetch ingredient metadata. "
            "Ensure Neo4j connection is configured."
        )
    
    # Convert all to strings for consistency
    str_ids = [str(iid) for iid in ingredient_ids]
    result = {}
    
    try:
        with _driver.session() as session:
            # Batch query using UNWIND for efficiency
            q = """
            UNWIND $ids AS ingredient_id
            MATCH (i:Ingredient) 
            WHERE i.id = ingredient_id OR i.proc_id = ingredient_id OR i.name = ingredient_id
            RETURN i.id AS id, 
                   i.proc_id AS proc_id,
                   i.name AS name,
                   i.category AS category,
                   i.perishability AS perishability,
                   i.shelf_life_days AS shelf_life_days
            """
            rows = session.run(q, ids=str_ids)
            for rec in rows:
                # Map by both id and proc_id so lookups work either way
                metadata = {
                    "id": rec["id"],
                    "proc_id": rec["proc_id"],
                    "name": rec["name"] or f"Ingredient-{rec['id']}",
                    "category": rec["category"] or "unknown",
                    "perishability": rec["perishability"] or "non_perishable",
                    "defaults": {
                        "shelf_life_days": int(rec["shelf_life_days"]) if rec["shelf_life_days"] else None
                    },
                }
                # Store by original id for lookup
                if rec["id"]:
                    result[rec["id"]] = metadata
                if rec["proc_id"]:
                    result[rec["proc_id"]] = metadata
            
            logger.info(f"Batch fetched metadata for {len(result)} ingredients from Neo4j")
            
            # Check if any ingredients were not found
            missing_ids = [iid for iid in str_ids if iid not in result]
            if missing_ids:
                raise ValueError(
                    f"Ingredients not found in Neo4j database: {', '.join(missing_ids[:5])}"
                    + (f" and {len(missing_ids) - 5} more" if len(missing_ids) > 5 else "")
                )
            
    except ValueError:
        # Re-raise ValueError as is
        raise
    except Exception as e:
        logger.exception(f"Error batch querying Neo4j for ingredients")
        raise RuntimeError(
            f"Failed to batch query Neo4j for ingredients: {str(e)}"
        ) from e
    
    return result


def suggest_substitutes(ingredient_id: str, limit: int = 5):
    """
    Return a list of substitute ingredient IDs for a given ingredient.

    Args:
        ingredient_id: Ingredient ID to find substitutes for
        limit: Maximum number of substitutes to return (default: 5)

    Returns:
        List of substitute ingredient IDs

    Raises:
        RuntimeError: If Neo4j driver is not available
        ValueError: If ingredient not found or has no substitutes
    """
    if _driver is None:
        raise RuntimeError(
            "Neo4j driver not initialized. Cannot fetch ingredient substitutes. "
            "Ensure Neo4j connection is configured."
        )
    
    try:
        with _driver.session() as session:
            q = (
                "MATCH (i:Ingredient {id: $id})-[:SUBSTITUTE]->(s:Ingredient) "
                "RETURN s.id AS id LIMIT $limit"
            )
            rows = session.run(q, id=str(ingredient_id), limit=limit)
            substitutes = [r["id"] for r in rows]
            
            if not substitutes:
                logger.warning(f"No substitutes found for ingredient {ingredient_id}")
                return []
            
            return substitutes
    except Exception as e:
        logger.exception(f"Error querying substitutes for {ingredient_id}")
        raise RuntimeError(
            f"Failed to query Neo4j for substitutes of '{ingredient_id}': {str(e)}"
        ) from e
