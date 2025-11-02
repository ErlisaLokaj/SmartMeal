from typing import Any, Dict, List, Optional
import re
import logging
from bson import ObjectId

# Use repositories for standard operations
from repositories import RecipeRepository
from adapters.sql_adapter import get_user_allergy_ingredient_ids

# NOTE: mongo_adapter still used for raw MongoDB operations in get_recipe_by_id and search_recipes
# These could be refactored to use RecipeRepository methods instead
from adapters import mongo_adapter

logger = logging.getLogger("smartmeal.recipe")


def _pub(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB document to public API format."""
    out = dict(doc)
    out["id"] = str(out.pop("_id"))
    if "name" not in out:
        out["name"] = out.get("title") or ""
    return out


UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _looks_like_uuid(s: str) -> bool:
    return bool(UUID_RE.match(s))


def get_recipe_by_id(recipe_id: str) -> Optional[Dict[str, Any]]:
    """Get a recipe by ID from MongoDB."""
    try:
        db = mongo_adapter._get_db()
        if db is None:
            logger.warning("MongoDB not available")
            return None

        recipes_collection = db["recipes"]

        # Try ObjectId first, then fall back to string ID in a single query
        q = {"_id": recipe_id}
        try:
            from bson import ObjectId

            q = {"_id": ObjectId(recipe_id)}
        except Exception:
            # If ObjectId conversion fails, use string ID
            pass

        doc = recipes_collection.find_one(q)
        if not doc:
            # If ObjectId query failed, try with string ID
            if "_id" in q and isinstance(q["_id"], ObjectId):
                doc = recipes_collection.find_one({"_id": recipe_id})

        return _pub(doc) if doc else None
    except Exception as e:
        logger.exception(f"Error fetching recipe {recipe_id}: {e}")
        return None


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
        and_clauses.append(
            {
                "$or": [
                    {"title": {"$regex": q, "$options": "i"}},
                    {
                        "ingredients": {
                            "$elemMatch": {"name": {"$regex": q, "$options": "i"}}
                        }
                    },
                ]
            }
        )

    if cuisine:
        or_cuisine: List[Dict[str, Any]] = []
        if _looks_like_uuid(cuisine):
            # пользователь передал cuisine_id
            or_cuisine.append({"cuisine_id": cuisine})
        else:
            or_cuisine.extend(
                [
                    {
                        "cuisine": {
                            "$regex": f"^{re.escape(cuisine)}$",
                            "$options": "i",
                        }
                    },  # точное имя кухни (если поле есть)
                    {
                        "tags": {"$elemMatch": {"$regex": cuisine, "$options": "i"}}
                    },  # иногда кухня кладётся в теги
                    {"title": {"$regex": cuisine, "$options": "i"}},  # как резерв
                    {"slug": {"$regex": cuisine, "$options": "i"}},
                ]
            )
        and_clauses.append({"$or": or_cuisine})

    if include:
        and_clauses.append(
            {
                "ingredients": {
                    "$elemMatch": {"name": {"$regex": include, "$options": "i"}}
                }
            }
        )

    if exclude:
        and_clauses.append(
            {
                "ingredients": {
                    "$not": {
                        "$elemMatch": {"name": {"$regex": exclude, "$options": "i"}}
                    }
                }
            }
        )

    if user_id:
        disallowed_ids = list(get_user_allergy_ingredient_ids(user_id))
        if disallowed_ids:
            # Use $nin directly on the ingredient_id field - simpler and more efficient
            and_clauses.append({"ingredients.ingredient_id": {"$nin": disallowed_ids}})

    mongo_query: Dict[str, Any] = {}
    if and_clauses:
        mongo_query = {"$and": and_clauses}

    try:
        db = mongo_adapter._get_db()
        if db is None:
            logger.warning("MongoDB not available, returning empty search results")
            return []

        recipes_collection = db["recipes"]
        cursor = (
            recipes_collection.find(mongo_query).skip(int(offset)).limit(int(limit))
        )

        results: List[Dict[str, Any]] = []
        for doc in cursor:
            results.append(_pub(doc))
        return results
    except Exception as e:
        logger.exception(f"Error searching recipes: {e}")
        return []
