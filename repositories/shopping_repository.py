"""
Shopping List Repository - Data access layer for shopping list operations
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from repositories.base import BaseRepository
from domain.models import ShoppingList, ShoppingListItem


class ShoppingListRepository(BaseRepository[ShoppingList]):
    """Repository for shopping list data access"""

    def __init__(self, db: Session):
        super().__init__(db, ShoppingList)

    def get_by_id(self, list_id: UUID) -> Optional[ShoppingList]:
        """Get shopping list by ID"""
        return (
            self.db.query(ShoppingList).filter(ShoppingList.list_id == list_id).first()
        )

    def get_by_user_id(self, user_id: UUID, limit: int = 20) -> List[ShoppingList]:
        """Get all shopping lists for a user"""
        return (
            self.db.query(ShoppingList)
            .filter(ShoppingList.user_id == user_id)
            .order_by(ShoppingList.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_by_id_and_user(
        self, list_id: UUID, user_id: UUID
    ) -> Optional[ShoppingList]:
        """Get shopping list by ID for specific user (authorization check)"""
        return (
            self.db.query(ShoppingList)
            .filter(ShoppingList.list_id == list_id, ShoppingList.user_id == user_id)
            .first()
        )

    def create(self, shopping_list: ShoppingList) -> ShoppingList:
        """Create a new shopping list"""
        self.db.add(shopping_list)
        self.db.commit()
        self.db.refresh(shopping_list)
        return shopping_list

    def delete_by_id_and_user(self, list_id: UUID, user_id: UUID) -> bool:
        """Delete shopping list (with authorization check)"""
        result = (
            self.db.query(ShoppingList)
            .filter(ShoppingList.list_id == list_id, ShoppingList.user_id == user_id)
            .delete()
        )
        self.db.commit()
        return result > 0


class ShoppingListItemRepository(BaseRepository[ShoppingListItem]):
    """Repository for shopping list item data access"""

    def __init__(self, db: Session):
        super().__init__(db, ShoppingListItem)

    def get_by_id(self, list_item_id: UUID) -> Optional[ShoppingListItem]:
        """Get shopping list item by ID"""
        return (
            self.db.query(ShoppingListItem)
            .filter(ShoppingListItem.list_item_id == list_item_id)
            .first()
        )

    def update(self, item: ShoppingListItem) -> ShoppingListItem:
        """Update shopping list item"""
        self.db.commit()
        self.db.refresh(item)
        return item

    def bulk_create(self, items: List[ShoppingListItem]) -> List[ShoppingListItem]:
        """Create multiple shopping list items"""
        self.db.add_all(items)
        self.db.commit()
        return items
