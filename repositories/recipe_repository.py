"""
Recipe Repository - Data access layer for recipe operations (MongoDB integration)
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from adapters import mongo_adapter


class RecipeRepository:
    """
    Repository for recipe data access from MongoDB.
    Wraps mongo_adapter functions for consistency with repository pattern.
    """

    def __init__(self, mongo_client=None):
        """Initialize repository with MongoDB client"""
        self.mongo_client = mongo_client

    def get_by_id(self, recipe_id: UUID) -> Optional[Dict[str, Any]]:
        """Get recipe by ID from MongoDB

        Args:
            recipe_id: Recipe UUID

        Returns:
            Recipe document or None if not found
        """
        return mongo_adapter.get_recipe(str(recipe_id))

    def search(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        exclude_ingredient_ids: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search recipes in MongoDB

        Args:
            query: Text search query (searches title)
            tags: List of tags to match (any)
            exclude_ingredient_ids: Ingredient IDs to exclude (allergies)
            limit: Maximum number of results

        Returns:
            List of recipe documents
        """
        return mongo_adapter.search_recipes(
            query=query,
            tags=tags,
            exclude_ingredient_ids=exclude_ingredient_ids,
            limit=limit,
        )

    def get_by_ingredients(
        self, ingredient_ids: List[UUID], limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Find recipes that can be made with given ingredients

        Args:
            ingredient_ids: List of ingredient UUIDs
            limit: Maximum number of results

        Returns:
            List of recipe documents
        """
        # Convert UUIDs to strings for MongoDB
        ingredient_id_strs = [str(iid) for iid in ingredient_ids]

        # Use search with ingredient filter
        # Note: This is a simple implementation - could be enhanced with scoring
        recipes = []
        for ingredient_id in ingredient_id_strs:
            found = mongo_adapter.get_recipes_using_ingredient(
                ingredient_id, limit=limit
            )
            recipes.extend(found)

        # Remove duplicates (recipes with multiple matching ingredients)
        seen = set()
        unique_recipes = []
        for recipe in recipes:
            recipe_id = recipe.get("_id")
            if recipe_id not in seen:
                seen.add(recipe_id)
                unique_recipes.append(recipe)

        return unique_recipes[:limit]

    def get_by_ids(self, recipe_ids: List[UUID]) -> List[Dict[str, Any]]:
        """Get multiple recipes by IDs

        Args:
            recipe_ids: List of recipe UUIDs

        Returns:
            List of recipe documents
        """
        recipe_id_strs = [str(rid) for rid in recipe_ids]
        return mongo_adapter.get_recipes_by_ids(recipe_id_strs)

    def get_random(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get random recipes for recommendations

        Args:
            limit: Maximum number of results

        Returns:
            List of recipe documents
        """
        return mongo_adapter.get_random_recipes(limit=limit)

    def aggregate_ingredients(
        self, recipe_ids: List[UUID], servings_list: List[float]
    ) -> Dict[str, Dict[str, Any]]:
        """Aggregate ingredients across multiple recipes for shopping lists

        Args:
            recipe_ids: List of recipe UUIDs
            servings_list: List of serving multipliers (same length as recipe_ids)

        Returns:
            Dict mapping ingredient_id to aggregated quantity info
        """
        recipe_id_strs = [str(rid) for rid in recipe_ids]
        return mongo_adapter.aggregate_ingredients(recipe_id_strs, servings_list)

    def delete(self, recipe_id: UUID) -> bool:
        """Delete recipe from MongoDB

        Note: Currently not implemented as recipe deletion
        requires careful consideration of data integrity.

        Args:
            recipe_id: Recipe UUID

        Returns:
            False (not implemented)
        """
        # Not implemented - recipes are typically soft-deleted or archived
        # rather than permanently removed to maintain data integrity
        return False
