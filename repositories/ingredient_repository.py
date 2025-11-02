"""
Ingredient Repository - Data access layer for ingredient operations (Neo4j integration)
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from adapters import graph_adapter


class IngredientRepository:
    """
    Repository for ingredient data access from Neo4j graph database.
    Wraps graph_adapter functions for consistency with repository pattern.
    """

    def __init__(self, neo4j_client=None):
        """Initialize repository with Neo4j client"""
        self.neo4j_client = neo4j_client

    def get_metadata(self, ingredient_id: str) -> Dict[str, Any]:
        """Get ingredient metadata from Neo4j

        Args:
            ingredient_id: Ingredient UUID as string

        Returns:
            Dict with ingredient metadata (name, category, etc.)

        Raises:
            RuntimeError: If Neo4j is unavailable
            ValueError: If ingredient not found
        """
        return graph_adapter.get_ingredient_meta(ingredient_id)

    def find_substitutes(
        self, ingredient_id: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find substitute ingredients from Neo4j

        Args:
            ingredient_id: Ingredient UUID as string
            limit: Maximum number of substitutes to return

        Returns:
            List of substitute ingredient dicts with metadata

        Raises:
            RuntimeError: If Neo4j is unavailable
        """
        return graph_adapter.find_substitutes(ingredient_id, limit=limit)

    def search_ingredients(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for ingredients by name

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of ingredient dicts matching the query
        """
        return graph_adapter.search_ingredients(query, limit=limit)

    def get_by_category(self, category: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all ingredients in a category

        Args:
            category: Category name
            limit: Maximum number of results

        Returns:
            List of ingredients in the category
        """
        return graph_adapter.get_ingredients_by_category(category, limit=limit)

    def validate_ingredient_exists(self, ingredient_id: str) -> bool:
        """Check if an ingredient exists in Neo4j

        Args:
            ingredient_id: Ingredient UUID as string

        Returns:
            True if ingredient exists, False otherwise
        """
        try:
            self.get_metadata(ingredient_id)
            return True
        except (RuntimeError, ValueError):
            return False

    def get_ingredients_batch(
        self, ingredient_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Get metadata for multiple ingredients in a single query

        Args:
            ingredient_ids: List of ingredient UUIDs as strings

        Returns:
            Dict mapping ingredient_id to metadata dict

        Raises:
            RuntimeError: If Neo4j is unavailable
            ValueError: If batch fetch fails
        """
        return graph_adapter.get_ingredients_batch(ingredient_ids)
