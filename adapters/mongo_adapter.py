"""MongoDB adapter for recipe storage and retrieval.
"""

from typing import Optional, Dict, List, Any
import logging
import os
from pymongo import MongoClient

logger = logging.getLogger("smartmeal.mongo")

_client = None
_db = None


# ------------------ Connection ------------------
def _get_db():
    """Lazy init DB connection."""
    global _client, _db
    if _db is not None:
        return _db
    uri = os.getenv("MONGO_URI", "mongodb://mongo:27017")
    dbname = os.getenv("MONGO_DB", "smartmeal")
    _client = MongoClient(uri)
    _db = _client[dbname]
    return _db


def connect(uri: str, db_name: str = "smartmeal"):
    global _client, _db
    try:
        _client = MongoClient(uri)
        _db = _client[db_name]
        _client.admin.command("ping")
        logger.info("Connected to MongoDB %s (database: %s)", uri, db_name)
    except Exception as exc:
        _client = None
        _db = None
        logger.warning(
            "Could not initialize MongoDB client: %s — falling back to stub", exc
        )


def close():
    """Close MongoDB connection."""
    global _client, _db
    try:
        if _client is not None:
            _client.close()
            logger.info("MongoDB client closed")
    except Exception:
        logger.exception("Error closing MongoDB client")
    finally:
        _client = None
        _db = None


def get_recipe(recipe_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single recipe by ID.

    Args:
        recipe_id: UUID string

    Returns:
        Recipe document or None if not found
    """
    if _db is not None:
        try:
            recipe = _db.recipes.find_one({"_id": recipe_id})
            if recipe:
                logger.debug(f"Recipe found: {recipe_id}")
                return recipe
            else:
                logger.debug(f"Recipe not found: {recipe_id}")
                return None
        except Exception:
            logger.exception(f"Error fetching recipe {recipe_id}")
            return None

    # Fallback stub
    logger.warning(f"MongoDB not available, returning None for {recipe_id}")
    return None


def search_recipes(
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        exclude_ingredient_ids: Optional[List[str]] = None,
        limit: int = 20
) -> List[Dict[str, Any]]:
    """Search recipes with filters.

    Args:
        query: Text search query (searches title)
        tags: List of tags to match (any)
        exclude_ingredient_ids: Ingredient IDs to exclude (allergies)
        limit: Maximum number of results

    Returns:
        List of recipe documents
    """
    if _db is not None:
        try:
            filter_query = {}

            # Text search on title
            if query:
                filter_query["title"] = {"$regex": query, "$options": "i"}

            # Tags filter (match any)
            if tags:
                filter_query["tags"] = {"$in": tags}

            # Exclude ingredients (for allergies)
            if exclude_ingredient_ids:
                filter_query["ingredients.ingredient_id"] = {
                    "$nin": exclude_ingredient_ids
                }

            recipes = list(_db.recipes.find(filter_query).limit(limit))
            logger.info(f"Found {len(recipes)} recipes matching filters")
            return recipes

        except Exception:
            logger.exception("Error searching recipes")
            return []

    # Fallback stub
    logger.warning("MongoDB not available, returning empty search results")
    return []


def get_recipes_by_ids(recipe_ids: List[str]) -> List[Dict[str, Any]]:
    """Fetch multiple recipes by IDs.

    Args:
        recipe_ids: List of recipe UUID strings

    Returns:
        List of recipe documents
    """
    if _db is not None:
        try:
            recipes = list(_db.recipes.find({"_id": {"$in": recipe_ids}}))
            logger.info(f"Fetched {len(recipes)} recipes by IDs")
            return recipes
        except Exception:
            logger.exception("Error fetching recipes by IDs")
            return []

    return []


def aggregate_ingredients(
        recipe_ids: List[str],
        servings_list: List[float]
) -> Dict[str, Dict[str, Any]]:
    """Aggregate ingredients across multiple recipes.

    This is used for shopping list generation.

    Args:
        recipe_ids: List of recipe IDs
        servings_list: List of serving multipliers (same length as recipe_ids)

    Returns:
        Dict mapping ingredient_id to aggregated quantity info:
        {
            "ingredient-uuid-1": {
                "ingredient_id": "uuid",
                "name": "chicken breast",
                "total_quantity": 600,
                "unit": "g",
                "from_recipes": ["recipe-1", "recipe-3"]
            }
        }
    """
    if _db is not None:
        try:
            aggregated = {}

            recipes = get_recipes_by_ids(recipe_ids)

            for recipe, target_servings in zip(recipes, servings_list):
                if not recipe:
                    continue

                recipe_servings = recipe.get("yields", {}).get("servings", 1)
                multiplier = target_servings / recipe_servings if recipe_servings > 0 else 1

                for ingredient in recipe.get("ingredients", []):
                    ing_id = ingredient.get("ingredient_id")
                    if not ing_id:
                        continue

                    quantity = ingredient.get("quantity", 0) * multiplier
                    unit = ingredient.get("unit", "")
                    name = ingredient.get("name", "unknown")

                    if ing_id not in aggregated:
                        aggregated[ing_id] = {
                            "ingredient_id": ing_id,
                            "name": name,
                            "total_quantity": 0,
                            "unit": unit,
                            "from_recipes": []
                        }

                    aggregated[ing_id]["total_quantity"] += quantity
                    if recipe.get("_id") not in aggregated[ing_id]["from_recipes"]:
                        aggregated[ing_id]["from_recipes"].append(recipe.get("_id"))

            logger.info(f"Aggregated {len(aggregated)} unique ingredients from {len(recipes)} recipes")
            return aggregated

        except Exception:
            logger.exception("Error aggregating ingredients")
            return {}

    # Fallback stub
    logger.warning("MongoDB not available, returning empty aggregation")
    return {}


def get_recipes_by_tags(tags: List[str], limit: int = 20) -> List[Dict[str, Any]]:
    """Get recipes matching any of the provided tags.
    """
    return search_recipes(tags=tags, limit=limit)


def get_recipes_using_ingredient(
        ingredient_id: str,
        limit: int = 10
) -> List[Dict[str, Any]]:
    """Find recipes that use a specific ingredient.
    """
    if _db is not None:
        try:
            recipes = list(
                _db.recipes.find(
                    {"ingredients.ingredient_id": ingredient_id}
                ).limit(limit)
            )
            logger.info(f"Found {len(recipes)} recipes using ingredient {ingredient_id}")
            return recipes
        except Exception:
            logger.exception(f"Error finding recipes with ingredient {ingredient_id}")
            return []

    return []


def get_random_recipes(limit: int = 10) -> List[Dict[str, Any]]:
    """Get random recipes (for recommendations)."""
    if _db is not None:
        try:
            # MongoDB aggregation pipeline for random sampling
            recipes = list(_db.recipes.aggregate([
                {"$sample": {"size": limit}}
            ]))
            logger.info(f"Retrieved {len(recipes)} random recipes")
            return recipes
        except Exception:
            logger.exception("Error getting random recipes")
            return []


# ------------------ Use cases 3-4 ------------------
def search_recipes_mongo(
        q: Optional[str] = None,
        cuisine: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
) -> List[Dict[str, Any]]:
    db = _get_db()
    col = db["recipes"]
    query: Dict[str, Any] = {}

    ors = []
    if q:
        ors.append({"title": {"$regex": q, "$options": "i"}})
        ors.append({"ingredients": {"$elemMatch": {"$regex": q, "$options": "i"}}})
    if ors:
        query["$or"] = ors
    if cuisine:
        query["cuisine"] = cuisine

    cursor = col.find(query, {"title": 1}).skip(max(offset, 0)).limit(max(limit, 1))
    results = []
    for doc in cursor:
        rid = str(doc.get("_id"))
        title = doc.get("title") or doc.get("name")
        if not title:
            continue
        results.append({"id": rid, "title": title})
    return results


def get_recipe_by_id_mongo(recipe_id: str) -> Optional[Dict[str, Any]]:
    db = _get_db()
    col = db["recipes"]
    doc = col.find_one({"_id": recipe_id})
    if not doc:
        return None
    return {
        "id": str(doc.get("_id")),
        "title": doc.get("title") or doc.get("name"),
        "ingredients": doc.get("ingredients") or [],
        "steps": doc.get("steps") or doc.get("directions") or [],
        "source": doc.get("source"),
        "cuisine": doc.get("cuisine"),
        "tags": doc.get("tags") or [],
        "images": doc.get("images") or [],
    }
