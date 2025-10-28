from typing import List
from sqlalchemy.orm import Session
import logging
import uuid

from core.database.models import PantryItem, AppUser
from core.schemas.profile_schemas import PantryItemCreate
from adapters import graph_adapter
from datetime import datetime, timedelta

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
            # If best_before is not provided, try to estimate using graph metadata
            bb = it.best_before
            try:
                if bb is None:
                    meta = graph_adapter.get_ingredient_meta(str(it.ingredient_id))
                    shelf_days = meta.get("defaults", {}).get("shelf_life_days") or 365
                    bb = datetime.utcnow().date() + timedelta(days=int(shelf_days))
            except Exception:
                bb = None

            db.add(
                PantryItem(
                    user_id=user_id,
                    ingredient_id=it.ingredient_id,
                    quantity=it.quantity,
                    unit=it.unit,
                    best_before=bb,
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
        # Estimate expiry if missing using Neo4j metadata
        bb = item.best_before
        try:
            if bb is None:
                meta = graph_adapter.get_ingredient_meta(str(item.ingredient_id))
                shelf_days = meta.get("defaults", {}).get("shelf_life_days") or 365
                bb = datetime.utcnow().date() + timedelta(days=int(shelf_days))
        except Exception:
            bb = None

        pi = PantryItem(
            user_id=user_id,
            ingredient_id=item.ingredient_id,
            quantity=item.quantity,
            unit=item.unit,
            best_before=bb,
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
