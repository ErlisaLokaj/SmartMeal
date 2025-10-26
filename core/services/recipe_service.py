"""Recipe service"""
from adapters.mongo_adapter import search_recipes_by_ingredient, search_recipes_by_name
from core.utils.helpers import rank_recipes, paginate
import logging
log = logging.getLogger("smartmeal.recipes")


def find_recipes_by_ingredient(ingredient: str, goal: str = "High Protein Meals", page: int = 1, size: int = 10):
    raw = search_recipes_by_ingredient(ingredient)
    ranked = rank_recipes(raw, goal, top_n=200)
    data, meta = paginate(ranked, page=page, size=size)
    log.info("recipes_by_ingredient ingredient=%s total=%d page=%d size=%d returned=%d",
             ingredient, len(ranked), page, size, len(data))
    return {"data": data, "meta": meta}

def find_recipes_by_name(name: str, page: int = 1, size: int = 10):
    raw = search_recipes_by_name(name)
    data, meta = paginate(raw, page=page, size=size)
    log.info("recipes_by_name name=%s total=%d page=%d size=%d returned=%d",
             name, len(raw), page, size, len(data))
    return {"data": data, "meta": meta}
