"""Adapter for Neo4j graph database."""
from neomodel import db
from core.models.graph_models import Ingredient
import logging

log = logging.getLogger("smartmeal.neo4j")


def get_substitutes(ingredient: str, limit: int = 5) -> list[str]:
    """
    Get substitute ingredients using OGM.

    Args:
        ingredient: Ingredient name to find substitutes for
        limit: Maximum number of substitutes to return

    Returns:
        List of substitute ingredient names
    """
    try:
        ing = Ingredient.nodes.get_or_none(name=ingredient.lower())
        if not ing:
            log.warning("ingredient_not_found name=%s", ingredient)
            return []

        subs = [s.name for s in ing.substitutes.all()[:limit]]
        log.info("substitutes_fetched ingredient=%s count=%d", ingredient, len(subs))
        return subs

    except Exception as e:
        log.error("get_substitutes_error ingredient=%s error=%s", ingredient, str(e))
        return []


def close():
    """Close Neo4j connection."""
    try:
        db.close_connection()
        log.info("neo4j_connection_closed")
    except Exception as e:
        log.error("neo4j_close_error error=%s", str(e))