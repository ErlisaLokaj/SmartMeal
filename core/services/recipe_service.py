from adapters.mongo_adapter import search_recipes
from adapters.graph_adapter import get_substitute

def find_recipes(ingredient: str):
    recipes = search_recipes(ingredient)
    substitutes = get_substitute(ingredient)
    return {"recipes": recipes, "alternatives": substitutes}
