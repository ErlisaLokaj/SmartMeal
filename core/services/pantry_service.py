from typing import List
from sqlalchemy.orm import Session
import logging
import uuid

from core.database.models import PantryItem, AppUser
from core.schemas.profile_schemas import PantryItemCreate

logger = logging.getLogger("smartmeal.pantry")


class PantryService:
    @staticmethod
    def get_pantry(db: Session, user_id: uuid.UUID) -> List[PantryItem]:
        return db.query(PantryItem).filter(PantryItem.user_id == user_id).all()

    @staticmethod
    def set_pantry(db: Session, user_id: uuid.UUID, items: List[PantryItemCreate]):
        # Replace all pantry items for a user
        user = db.query(AppUser).filter(AppUser.user_id == user_id).first()
        if not user:
            raise ValueError(f"User not found: {user_id}")

        # Delete existing
        db.query(PantryItem).filter(PantryItem.user_id == user_id).delete()
        # Insert new
        for it in items:
            db.add(
                PantryItem(
                    user_id=user_id,
                    ingredient_id=it.ingredient_id,
                    quantity=it.quantity,
                    unit=it.unit,
                    best_before=it.best_before,
                    source=None,
                )
            )
        db.commit()
        return db.query(PantryItem).filter(PantryItem.user_id == user_id).all()

    @staticmethod
    def add_item(db: Session, user_id: uuid.UUID, item: PantryItemCreate):
        user = db.query(AppUser).filter(AppUser.user_id == user_id).first()
        if not user:
            raise ValueError(f"User not found: {user_id}")
        pi = PantryItem(
            user_id=user_id,
            ingredient_id=item.ingredient_id,
            quantity=item.quantity,
            unit=item.unit,
            best_before=item.best_before,
            source=None,
        )
        db.add(pi)
        db.commit()
        db.refresh(pi)
        return pi

    @staticmethod
    def remove_item(db: Session, pantry_item_id: uuid.UUID) -> bool:
        res = (
            db.query(PantryItem)
            .filter(PantryItem.pantry_item_id == pantry_item_id)
            .delete()
        )
        if res:
            db.commit()
            return True
        return False
