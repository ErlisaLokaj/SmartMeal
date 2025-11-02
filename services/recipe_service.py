from typing import Any, Dict, List, Optional
import re
import logging
from bson import ObjectId

# Use our adapters instead of direct connections
from adapters.mongo_adapter import mongo_adapter
from adapters.sql_adapter import get_user_allergy_ingredient_ids

logger = logging.getLogger("smartmeal.recipe")


def _pub(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB document to public API format."""
    out = dict(doc)
    out["id"] = str(out.pop("_id"))
    if "name" not in out:
        out["name"] = out.get("title") or ""
    return out
    return out

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

def _looks_like_uuid(s: str) -> bool:
    return bool(UUID_RE.match(s))

def get_recipe_by_id(recipe_id: str) -> Optional[Dict[str, Any]]:
    """Get a recipe by ID from MongoDB."""
    recipes_collection = mongo_adapter.get_collection("recipes")
    
    q = {"_id": recipe_id}
    try:
        q = {"_id": ObjectId(recipe_id)}
    except Exception:
        pass

    doc = recipes_collection.find_one(q) or recipes_collection.find_one({"_id": recipe_id})
    return _pub(doc) if doc else None


def search_recipes(
        user_id: Optional[str] = None,
        q: Optional[str] = None,
        cuisine: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        include: Optional[str] = None,
        exclude: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Recipe search without using $text to avoid relying on Mongo indexes.
    - q searches by title AND by ingredients.name (both by regex, case-insensitive)
    - cuisine — exact match
    - include — requires the presence of an ingredient by name (regex)
    - exclude — excludes recipes where the ingredient by name is found (regex)
    - user_id — excludes recipes containing ingredients from user_allergy (by ingredient_id)
    """
    and_clauses: List[Dict[str, Any]] = []

    if q:
        and_clauses.append({
            "$or": [
                {"title": {"$regex": q, "$options": "i"}},
                {"ingredients": {"$elemMatch": {"name": {"$regex": q, "$options": "i"}}}},
            ]
        })

    if cuisine:
        or_cuisine: List[Dict[str, Any]] = []
        if _looks_like_uuid(cuisine):
            # пользователь передал cuisine_id
            or_cuisine.append({"cuisine_id": cuisine})
        else:
            or_cuisine.extend([
                {"cuisine": {"$regex": f"^{re.escape(cuisine)}$", "$options": "i"}},       # точное имя кухни (если поле есть)
                {"tags":    {"$elemMatch": {"$regex": cuisine, "$options": "i"}}},         # иногда кухня кладётся в теги
                {"title":   {"$regex": cuisine, "$options": "i"}},                          # как резерв
                {"slug":    {"$regex": cuisine, "$options": "i"}},
            ])
        and_clauses.append({"$or": or_cuisine})

    if include:
        and_clauses.append({
            "ingredients": {
                "$elemMatch": {
                    "name": {"$regex": include, "$options": "i"}
                }
            }
        })

    if exclude:
        and_clauses.append({
            "ingredients": {
                "$not": {
                    "$elemMatch": {
                        "name": {"$regex": exclude, "$options": "i"}
                    }
                }
            }
        })

    if user_id:
        disallowed_ids = list(get_user_allergy_ingredient_ids(user_id))
        if disallowed_ids:
            and_clauses.append({
                "ingredients": {
                    "$not": {
                        "$elemMatch": {
                            "ingredient_id": {"$in": disallowed_ids}
                        }
                    }
                }
            })

    mongo_query: Dict[str, Any] = {}
    if and_clauses:
        mongo_query = {"$and": and_clauses}

    recipes_collection = mongo_adapter.get_collection("recipes")
    cursor = recipes_collection.find(mongo_query).skip(int(offset)).limit(int(limit))

    results: List[Dict[str, Any]] = []
    for doc in cursor:
        results.append(_pub(doc))
    return results
