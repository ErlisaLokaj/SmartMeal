from typing import List
from sqlalchemy.orm import Session
import logging
import uuid
from decimal import Decimal, InvalidOperation

from core.database.models import PantryItem, AppUser
from core.schemas.profile_schemas import PantryItemCreate
from adapters import graph_adapter
from datetime import datetime, timedelta, date
from core.exceptions import NotFoundError

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
            raise NotFoundError(f"User not found: {user_id}")
        # Replace all items in a transaction so the delete+insert is atomic
        try:
            with db.begin():
                db.query(PantryItem).filter(PantryItem.user_id == user_id).delete()
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
                        logger.warning("Failed to fetch ingredient meta for %s; leaving best_before unset", it.ingredient_id)

                    qty = None
                    try:
                        qty = Decimal(str(it.quantity))
                    except (InvalidOperation, TypeError):
                        qty = Decimal("0")

                    db.add(
                        PantryItem(
                            user_id=user_id,
                            ingredient_id=it.ingredient_id,
                            quantity=qty,
                            unit=it.unit,
                            best_before=bb,
                            source=None,
                        )
                    )

            return db.query(PantryItem).filter(PantryItem.user_id == user_id).all()
        except Exception:
            logger.exception("Error setting pantry for user %s", user_id)
            raise

    @staticmethod
    def add_item(db: Session, user_id: uuid.UUID, item: PantryItemCreate):
        user = db.query(AppUser).filter(AppUser.user_id == user_id).first()
        if not user:
            raise NotFoundError(f"User not found: {user_id}")
        # perform the upsert inside a transaction to ensure lock and write are atomic
        try:
            with db.begin():
                try:
                    existing = (
                        db.query(PantryItem)
                        .filter(
                            PantryItem.user_id == user_id,
                            PantryItem.ingredient_id == item.ingredient_id,
                            PantryItem.unit == item.unit,
                        )
                        .with_for_update()
                        .first()
                    )
                except Exception:
                    # Some backends don't support with_for_update; fallback to simple lookup
                    existing = (
                        db.query(PantryItem)
                        .filter(
                            PantryItem.user_id == user_id,
                            PantryItem.ingredient_id == item.ingredient_id,
                            PantryItem.unit == item.unit,
                        )
                        .first()
                    )

                # Estimate expiry if missing using Neo4j metadata
                bb = item.best_before
                try:
                    if bb is None:
                        meta = graph_adapter.get_ingredient_meta(str(item.ingredient_id))
                        shelf_days = meta.get("defaults", {}).get("shelf_life_days") or 365
                        bb = datetime.utcnow().date() + timedelta(days=int(shelf_days))
                except Exception:
                    bb = None
                    logger.warning("Failed to fetch ingredient meta for %s; leaving best_before unset", item.ingredient_id)

                if existing:
                    # increment quantity and possibly update best_before
                    try:
                        existing_qty = Decimal(existing.quantity)
                    except Exception:
                        existing_qty = Decimal(str(float(existing.quantity)))

                    try:
                        add_qty = Decimal(str(item.quantity))
                    except (InvalidOperation, TypeError):
                        add_qty = Decimal("0")

                    existing.quantity = existing_qty + add_qty
                    if item.best_before is not None:
                        existing.best_before = item.best_before
                    elif existing.best_before is None:
                        existing.best_before = bb
                    db.add(existing)
                    # row will be committed by context
                    db.refresh(existing)
                    return existing

                # create new
                try:
                    qty = Decimal(str(item.quantity))
                except (InvalidOperation, TypeError):
                    qty = Decimal("0")

                pi = PantryItem(
                    user_id=user_id,
                    ingredient_id=item.ingredient_id,
                    quantity=qty,
                    unit=item.unit,
                    best_before=bb,
                    source=None,
                )
                db.add(pi)
                db.flush()
                db.refresh(pi)
                return pi
        except Exception:
            logger.exception("Error adding pantry item for user %s", user_id)
            raise

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
