"""Service for generating a plan for a given ingredient."""
from adapters.sql_adapter import get_user, get_pantry
from adapters.mongo_adapter import search_recipes_by_ingredient
from adapters.graph_adapter import get_substitutes
from core.utils.helpers import rank_recipes, build_shopping_list

def generate_plan_for_ingredient(user_name: str, ingredient: str, top_n: int = 10):
    user = get_user(user_name) or {"name": user_name, "goal": "Balanced"}
    recipes = search_recipes_by_ingredient(ingredient)
    ranked = rank_recipes(recipes, user["goal"], top_n=top_n)
    subs = get_substitutes(ingredient)  # requires Neo4j data loaded
    pantry = get_pantry(user_name)
    shopping = build_shopping_list(ranked, pantry=pantry)
    return {
        "user": user["name"],
        "goal": user["goal"],
        "ingredient": ingredient,
        "recipes": ranked,
        "substitutes": subs,
        "pantry": pantry,
        "shopping_list": shopping
    }
