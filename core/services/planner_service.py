"""Service for generating a plan for a given ingredient."""
from adapters.sql_adapter import get_user, get_pantry
from adapters.mongo_adapter import search_recipes_by_ingredient
from adapters.graph_adapter import get_substitutes, link_recipe
from core.utils.helpers import rank_recipes, build_shopping_list, normalize_ingredients
from fastapi import HTTPException
import logging

log = logging.getLogger("smartmeal.planner")


def generate_plan_for_ingredient(user_name: str, ingredient: str, top_n: int = 10):
    """Generate a personalized meal plan and automatically link recipes to graph."""
    user = get_user(user_name)
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"User '{user_name}' not found. Please create the user first."
        )

    recipes = search_recipes_by_ingredient(ingredient)
    ranked = rank_recipes(recipes, user["goal"], top_n=top_n)

    for recipe in ranked:
        recipe_name = recipe.get("name", "")
        ingredients = recipe.get("ingredients", [])
        normalized = normalize_ingredients(ingredients)
        link_recipe(recipe_name, normalized)

    subs = get_substitutes(ingredient)

    pantry = get_pantry(user_name)
    shopping = build_shopping_list(ranked, pantry=pantry)

    log.info(
        "plan_generated user=%s goal=%s ingredient=%s recipes=%d substitutes=%d pantry_items=%d need=%d have=%d linked_to_graph=%d",
        user["name"], user["goal"], ingredient, len(ranked), len(subs), len(pantry),
        len(shopping.get('need', [])), len(shopping.get('have', [])), len(ranked)
    )

    return {
        "user": user["name"],
        "goal": user["goal"],
        "ingredient": ingredient,
        "recipes": ranked,
        "substitutes": subs,
        "pantry": pantry,
        "shopping_list": shopping
    }