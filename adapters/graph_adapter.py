"""Adapter for Neo4j graph database."""
from neomodel import db
from core.models.graph_models import Ingredient, Recipe
import logging

log = logging.getLogger("smartmeal.neo4j")


def get_substitutes(ingredient: str, limit: int = 5) -> list[str]:
    """Get substitute ingredients."""
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


def link_recipe(recipe_name: str, ingredients: list[str]):
    """Link recipe to ingredients in Neo4j graph."""
    try:
        recipe = Recipe.get_or_create({"name": recipe_name.lower()})[0]

        for ing_name in ingredients:
            ingredient = Ingredient.get_or_create({"name": ing_name.lower()})[0]
            if not recipe.contains.is_connected(ingredient):
                recipe.contains.connect(ingredient)

        log.info("recipe_linked name=%s ingredients=%d", recipe_name, len(ingredients))
        return True

    except Exception as e:
        log.error("link_recipe_error name=%s error=%s", recipe_name, str(e))
        return False


def close():
    """Close Neo4j connection."""
    try:
        db.close_connection()
        log.info("neo4j_connection_closed")
    except Exception as e:
        log.error("neo4j_close_error error=%s", str(e))