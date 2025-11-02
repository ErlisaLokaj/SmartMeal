"""
Ingredient SQL Repository - Data access layer for PostgreSQL ingredient master table
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from domain.models.ingredient import Ingredient
from repositories.base import BaseRepository


class IngredientSQLRepository(BaseRepository[Ingredient]):
    """Repository for ingredient master data in PostgreSQL"""

    def __init__(self, db: Session):
        super().__init__(db, Ingredient)

    def get_by_id(self, ingredient_id: UUID) -> Optional[Ingredient]:
        """Get ingredient by ID"""
        return (
            self.db.query(Ingredient)
            .filter(Ingredient.ingredient_id == ingredient_id)
            .first()
        )

    def get_by_name(self, name: str) -> Optional[Ingredient]:
        """Get ingredient by name (case-insensitive)"""
        normalized_name = name.lower().strip()
        return (
            self.db.query(Ingredient)
            .filter(func.lower(Ingredient.name) == normalized_name)
            .first()
        )

    def get_or_create(self, name: str) -> Ingredient:
        """
        Get existing ingredient by name, or create if it doesn't exist.

        Handles race conditions with IntegrityError retry.

        Args:
            name: Ingredient name

        Returns:
            Ingredient instance (existing or newly created)
        """
        normalized_name = name.lower().strip()

        # Try to find existing
        ingredient = self.get_by_name(normalized_name)
        if ingredient:
            return ingredient

        # Create new if not found
        ingredient = Ingredient(name=normalized_name)
        self.db.add(ingredient)

        try:
            self.db.commit()
            self.db.refresh(ingredient)
            return ingredient
        except IntegrityError:
            # Race condition - another request created it
            self.db.rollback()
            # Fetch the one that was created
            return self.get_by_name(normalized_name)

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Ingredient]:
        """Get all ingredients with pagination"""
        return (
            self.db.query(Ingredient)
            .order_by(Ingredient.name)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def search_by_name(self, query: str, limit: int = 20) -> List[Ingredient]:
        """Search ingredients by name (case-insensitive partial match)"""
        search_pattern = f"%{query.lower()}%"
        return (
            self.db.query(Ingredient)
            .filter(func.lower(Ingredient.name).like(search_pattern))
            .order_by(Ingredient.name)
            .limit(limit)
            .all()
        )

    def bulk_create_if_not_exists(self, names: List[str]) -> List[Ingredient]:
        """
        Bulk create ingredients that don't exist yet.

        Args:
            names: List of ingredient names

        Returns:
            List of Ingredient instances (mix of existing and newly created)
        """
        results = []

        for name in names:
            normalized_name = name.lower().strip()

            # Check if exists
            ingredient = self.get_by_name(normalized_name)

            if ingredient:
                results.append(ingredient)
            else:
                # Create new
                ingredient = Ingredient(name=normalized_name)
                self.db.add(ingredient)

        # Commit all at once
        try:
            self.db.commit()
            # Refresh all new items
            for ingredient in results:
                if ingredient not in results:  # Only new ones
                    self.db.refresh(ingredient)
        except IntegrityError:
            # Handle race conditions
            self.db.rollback()
            # Re-fetch all
            results = [self.get_by_name(name.lower().strip()) for name in names]

        return results
