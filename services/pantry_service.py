from typing import List, Dict, Any
from sqlalchemy.orm import Session
import logging
import uuid
from decimal import Decimal, InvalidOperation

from domain.models import PantryItem, AppUser
from domain.schemas.profile_schemas import PantryItemCreate
from repositories import IngredientRepository, PantryRepository, UserRepository
from datetime import datetime, timedelta, date
from app.exceptions import NotFoundError, ServiceValidationError

logger = logging.getLogger("smartmeal.pantry")


class PantryService:
    @staticmethod
    def validate_ingredient_data(ingredient_id: uuid.UUID) -> Dict[str, Any]:
        """
        Validate that an ingredient exists in Neo4j and return its metadata.
        """
        ingredient_repo = IngredientRepository()
        try:
            meta = ingredient_repo.get_metadata(str(ingredient_id))
            return meta
        except RuntimeError as e:
            raise ServiceValidationError(
                f"Invalid ingredient {ingredient_id}: Neo4j database not available. {e}"
            )
        except ValueError as e:
            raise ServiceValidationError(
                f"Invalid ingredient {ingredient_id}: Ingredient not found in catalog. {e}"
            )

    @staticmethod
    def validate_ingredients_batch(
        ingredient_ids: List[uuid.UUID],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Validate multiple ingredients in a single batch query.
        """
        if not ingredient_ids:
            return {}

        ingredient_repo = IngredientRepository()
        try:
            id_strings = [str(iid) for iid in ingredient_ids]
            meta_map = ingredient_repo.get_ingredients_batch(id_strings)
            return meta_map
        except RuntimeError as e:
            raise ServiceValidationError(
                f"Cannot validate ingredients: Neo4j database not available. {e}"
            )
        except ValueError as e:
            raise ServiceValidationError(
                f"Cannot validate ingredients: Some ingredients not found in catalog. {e}"
            )

    @staticmethod
    def get_pantry(db: Session, user_id: uuid.UUID) -> List[PantryItem]:
        pantry_repo = PantryRepository(db)
        return pantry_repo.get_by_user_id(user_id)

    @staticmethod
    def set_pantry(db: Session, user_id: uuid.UUID, items: List[PantryItemCreate]):
        """
        Replace all pantry items for a user with batch ingredient validation.
        """

        user_repo = UserRepository(db)
        pantry_repo = PantryRepository(db)

        user = user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")


        if items:
            ingredient_ids = [it.ingredient_id for it in items]
            meta_map = PantryService.validate_ingredients_batch(ingredient_ids)
            logger.info(
                f"Validated {len(meta_map)} ingredients in batch for user {user_id}"
            )
        else:
            meta_map = {}

        try:
            existing_items = pantry_repo.get_by_user_id(user_id)
            for item in existing_items:
                db.delete(item)

            for it in items:
                meta = meta_map.get(str(it.ingredient_id), {})

                bb = it.best_before
                if bb is None:
                    shelf_days = meta.get("defaults", {}).get("shelf_life_days")
                    if shelf_days:
                        bb = datetime.utcnow().date() + timedelta(days=int(shelf_days))
                        logger.debug(
                            f"Estimated best_before for {it.ingredient_id}: {bb} "
                            f"(+{shelf_days} days)"
                        )
                    else:
                        logger.debug(
                            f"No shelf_life_days for {it.ingredient_id}; "
                            "best_before will be None"
                        )

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

            db.commit()
            return pantry_repo.get_by_user_id(user_id)
        except Exception:
            db.rollback()
            logger.exception("Error setting pantry for user %s", user_id)
            raise

    @staticmethod
    def add_item(db: Session, user_id: uuid.UUID, item: PantryItemCreate):
        """
        Add or update a pantry item for a user with ingredient validation.
        """

        user_repo = UserRepository(db)

        user = user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        meta = PantryService.validate_ingredient_data(item.ingredient_id)
        if meta is None:
            raise ServiceValidationError(
                f"Ingredient not found in Neo4j: {item.ingredient_id}"
            )

        bb = item.best_before
        if bb is None:
            shelf_days = meta.get("defaults", {}).get("shelf_life_days")
            if shelf_days:
                bb = datetime.utcnow().date() + timedelta(days=int(shelf_days))
                logger.info(
                    f"Estimated best_before for {item.ingredient_id}: {bb} "
                    f"(+{shelf_days} days from Neo4j)"
                )
            else:
                logger.warning(
                    f"No shelf_life_days in Neo4j for {item.ingredient_id}; "
                    "best_before will be None"
                )


        try:
            pantry_repo = PantryRepository(db)

            existing = pantry_repo.get_batch(
                user_id=user_id,
                ingredient_id=item.ingredient_id,
                unit=item.unit,
                best_before=bb,
                with_lock=True,
            )

            if existing:
                try:
                    existing_qty = Decimal(existing.quantity)
                except Exception:
                    existing_qty = Decimal(str(float(existing.quantity)))

                try:
                    add_qty = Decimal(str(item.quantity))
                except (InvalidOperation, TypeError):
                    add_qty = Decimal("0")

                existing.quantity = existing_qty + add_qty
                logger.info(
                    f"Merged quantity for existing batch: {item.ingredient_id} "
                    f"expiry={bb}, new_qty={existing.quantity}"
                )
                db.add(existing)
                db.commit()
                db.refresh(existing)
                return existing

            try:
                qty = Decimal(str(item.quantity))
            except (InvalidOperation, TypeError):
                qty = Decimal("0")

            logger.info(
                f"Creating new pantry batch: {item.ingredient_id} "
                f"qty={qty}, expiry={bb}"
            )
            pi = PantryItem(
                user_id=user_id,
                ingredient_id=item.ingredient_id,
                quantity=qty,
                unit=item.unit,
                best_before=bb,
                source=None,
            )
            db.add(pi)
            db.commit()
            db.refresh(pi)
            return pi
        except Exception:
            db.rollback()
            logger.exception("Error adding pantry item for user %s", user_id)
            raise

    @staticmethod
    def remove_item(db: Session, pantry_item_id: uuid.UUID) -> bool:
        pantry_repo = PantryRepository(db)
        return pantry_repo.delete_by_id(pantry_item_id)

    @staticmethod
    def update_quantity(
        db: Session,
        pantry_item_id: uuid.UUID,
        quantity_change: Decimal,
        reason: str = None,
    ) -> PantryItem:
        """
        Update the quantity of a specific pantry item.

        Supports both positive (add/restock) and negative (consume/waste) changes.
        This is the primary method for tracking daily pantry usage.
        """
        pantry_repo = PantryRepository(db)
        item = pantry_repo.get_by_id(pantry_item_id)

        if not item:
            raise NotFoundError(f"Pantry item {pantry_item_id} not found")

        try:
            current_qty = Decimal(str(item.quantity))
            change = Decimal(str(quantity_change))
            new_qty = current_qty + change
        except (InvalidOperation, TypeError) as e:
            raise ServiceValidationError(f"Invalid quantity values: {e}")

        if new_qty < 0:
            raise ServiceValidationError(
                f"Cannot update quantity: result would be negative "
                f"(current={current_qty}, change={change}, result={new_qty}). "
                f"Current stock insufficient."
            )

        if new_qty == 0:
            logger.info(
                f"Auto-removing pantry item {pantry_item_id} (quantity reached 0). "
                f"Reason: {reason or 'not specified'}"
            )
            pantry_repo.delete_by_id(pantry_item_id)
            return None

        item = pantry_repo.update_quantity(pantry_item_id, new_qty)
        logger.info(
            f"Updated pantry item {pantry_item_id}: "
            f"{current_qty} → {new_qty} (change={change}). "
            f"Reason: {reason or 'not specified'}"
        )

        return item

    @staticmethod
    def get_expiring_soon(
        db: Session, user_id: uuid.UUID, days_threshold: int = 3
    ) -> List[PantryItem]:
        """
        Get pantry items expiring within the specified number of days.

        This is critical for FIFO/FEFO inventory management and waste prevention.
        Helps users prioritize which ingredients to cook with first.
        """
        pantry_repo = PantryRepository(db)
        items = pantry_repo.get_expiring_items(user_id, days_threshold)

        logger.info(
            f"Found {len(items)} items expiring within {days_threshold} days "
            f"for user {user_id}"
        )
        return items
