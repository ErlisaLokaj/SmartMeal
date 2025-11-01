"""Health check and utility routes"""

from fastapi import APIRouter
import logging

from adapters import graph_adapter

router = APIRouter(tags=["Health"])
logger = logging.getLogger("smartmeal.api.health")


@router.get("/health-check")
def health_check():
    """Basic health check endpoint"""
    return {"status": "ok", "service": "SmartMeal"}


@router.get("/neo4j/seed-status")
def neo4j_seed_status():
    """Return a simple count of Ingredient nodes in Neo4j."""
    try:
        # Attempt to query Neo4j for ingredient count
        if getattr(graph_adapter, "_driver", None) is not None:
            with graph_adapter._driver.session() as s:
                r = s.run("MATCH (n:Ingredient) RETURN count(n) AS cnt")
                cnt = r.single().get("cnt")
                return {"neo4j_ingredient_count": int(cnt)}
        # driver not present — return not available
        return {"neo4j_ingredient_count": None, "note": "driver not configured"}
    except Exception as e:
        logger.exception("Error checking Neo4j seed status")
        return {"neo4j_ingredient_count": None, "error": str(e)}
