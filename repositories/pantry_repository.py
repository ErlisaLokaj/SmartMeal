"""
Pantry Repository - Data access layer for pantry operations
"""

from typing import List, Optional
from uuid import UUID
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import and_

from repositories.base import BaseRepository
from domain.models import PantryItem


class PantryRepository(BaseRepository[PantryItem]):
    """Repository for pantry item data access"""

    def __init__(self, db: Session):
        super().__init__(db, PantryItem)

    def get_by_id(self, pantry_item_id: UUID) -> Optional[PantryItem]:
        """Get pantry item by ID"""
        return (
            self.db.query(PantryItem)
            .filter(PantryItem.pantry_item_id == pantry_item_id)
            .first()
        )

    def get_by_user_id(self, user_id: UUID) -> List[PantryItem]:
        """Get all pantry items for a user"""
        return self.db.query(PantryItem).filter(PantryItem.user_id == user_id).all()

    def get_by_user_and_ingredient(
        self, user_id: UUID, ingredient_id: UUID, unit: str = None
    ) -> Optional[PantryItem]:
        """Get pantry item by user, ingredient, and optionally unit"""
        query = self.db.query(PantryItem).filter(
            and_(
                PantryItem.user_id == user_id,
                PantryItem.ingredient_id == ingredient_id,
            )
        )
        if unit:
            query = query.filter(PantryItem.unit == unit)
        return query.first()

    def get_batch(
        self,
        user_id: UUID,
        ingredient_id: UUID,
        unit: str,
        best_before: date = None,
        with_lock: bool = False,
    ) -> Optional[PantryItem]:
        """Get pantry item matching user, ingredient, unit, and best_before (batch)"""
        query = self.db.query(PantryItem).filter(
            and_(
                PantryItem.user_id == user_id,
                PantryItem.ingredient_id == ingredient_id,
                PantryItem.unit == unit,
                PantryItem.best_before == best_before,
            )
        )
        if with_lock:
            try:
                query = query.with_for_update()
            except Exception:
                # Some backends don't support with_for_update
                pass
        return query.first()

    def get_expiring_items(self, user_id: UUID, within_days: int) -> List[PantryItem]:
        """Get pantry items expiring within specified days"""
        from datetime import datetime, timedelta

        cutoff_date = datetime.utcnow().date() + timedelta(days=within_days)
        return (
            self.db.query(PantryItem)
            .filter(
                and_(
                    PantryItem.user_id == user_id,
                    PantryItem.best_before.isnot(None),
                    PantryItem.best_before <= cutoff_date,
                )
            )
            .order_by(PantryItem.best_before)
            .all()
        )

    def create_or_update(
        self,
        user_id: UUID,
        ingredient_id: UUID,
        quantity,
        unit: str = None,
        best_before: date = None,
        source: str = None,
    ) -> PantryItem:
        """Create or update pantry item (upsert logic)"""
        existing = self.get_by_user_and_ingredient(user_id, ingredient_id, unit)

        if existing:
            # Update existing item
            existing.quantity += quantity
            if best_before:
                existing.best_before = best_before
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            # Create new item
            item = PantryItem(
                user_id=user_id,
                ingredient_id=ingredient_id,
                quantity=quantity,
                unit=unit,
                best_before=best_before,
                source=source,
            )
            self.db.add(item)
            self.db.commit()
            self.db.refresh(item)
            return item

    def delete_by_id(self, pantry_item_id: UUID) -> bool:
        """Delete pantry item by ID"""
        item = self.get_by_id(pantry_item_id)
        if item:
            self.db.delete(item)
            self.db.commit()
            return True
        return False

    def update_quantity(
        self, pantry_item_id: UUID, new_quantity, commit: bool = True
    ) -> Optional[PantryItem]:
        """Update quantity of a pantry item"""
        item = self.get_by_id(pantry_item_id)
        if item:
            item.quantity = new_quantity
            if commit:
                self.db.commit()
                self.db.refresh(item)
            return item
        return None

    def delete_by_user_id(self, user_id: UUID) -> int:
        """Delete all pantry items for a user"""
        count = self.db.query(PantryItem).filter(PantryItem.user_id == user_id).delete()
        self.db.commit()
        return count
