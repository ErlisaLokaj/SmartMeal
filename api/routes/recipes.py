"""
Recipe routes - Recipe search and retrieval endpoints.
Implements use cases 3 (recipe search) and 6 (recipe viewing).
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
import logging

from services.recipe_service import get_recipe_by_id, search_recipes

router = APIRouter(prefix="/recipes", tags=["Recipes"])
logger = logging.getLogger("smartmeal.api.recipes")


@router.get("", response_model=List[Dict[str, Any]])
def search_recipes_endpoint(
    q: Optional[str] = Query(
        default=None, description="Search query for title or ingredients"
    ),
    cuisine: Optional[str] = Query(default=None, description="Cuisine filter"),
    include: Optional[str] = Query(default=None, description="Must include ingredient"),
    exclude: Optional[str] = Query(default=None, description="Must exclude ingredient"),
    user_id: Optional[str] = Query(
        default=None, description="User ID for allergy filtering"
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> List[Dict[str, Any]]:
    """
    Search recipes with filters.

    - **q**: Search in title and ingredient names
    - **cuisine**: Filter by cuisine type
    - **include**: Must contain this ingredient
    - **exclude**: Must NOT contain this ingredient
    - **user_id**: Exclude recipes with user's allergens
    - **limit**: Max results (1-100)
    - **offset**: For pagination
    """
    try:
        results = search_recipes(
            user_id=user_id,
            q=q,
            cuisine=cuisine,
            limit=limit,
            offset=offset,
            include=include,
            exclude=exclude,
        )
        return results
    except Exception as e:
        logger.exception("Error searching recipes")
        raise HTTPException(status_code=500, detail=f"Recipe search failed: {str(e)}")


@router.get("/{recipe_id}", response_model=Dict[str, Any])
def get_recipe(recipe_id: str) -> Dict[str, Any]:
    """
    Get a single recipe by ID.

    Returns full recipe details including ingredients, steps, and nutrition.
    """
    # Validate recipe_id format (UUID or MongoDB ObjectId)
    if not recipe_id or len(recipe_id) > 100:
        raise HTTPException(status_code=400, detail="Invalid recipe ID format")

    try:
        recipe = get_recipe_by_id(recipe_id)
        if not recipe:
            raise HTTPException(status_code=404, detail=f"Recipe {recipe_id} not found")
        return recipe
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching recipe {recipe_id}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch recipe: {str(e)}")
