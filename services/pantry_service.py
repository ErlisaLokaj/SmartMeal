from typing import List, Dict, Any
from sqlalchemy.orm import Session
import logging
import uuid
from decimal import Decimal, InvalidOperation

from domain.models import PantryItem, AppUser
from domain.schemas.profile_schemas import PantryItemCreate
from adapters import graph_adapter
from datetime import datetime, timedelta, date
from core.exceptions import NotFoundError, ServiceValidationError

logger = logging.getLogger("smartmeal.pantry")


class PantryService:
    @staticmethod
    def validate_ingredient_data(ingredient_id: uuid.UUID) -> Dict[str, Any]:
        """
        Validate that an ingredient exists in Neo4j and return its metadata.

        This validation ensures data integrity by checking that the ingredient
        exists before adding it to the pantry. No fake fallback data is used.

        Args:
            ingredient_id: UUID of the ingredient to validate

        Returns:
            Dict with ingredient metadata including name, category, perishability,
            and shelf_life_days for expiry estimation

        Raises:
            ServiceValidationError: If Neo4j is unavailable or ingredient not found
        """
        try:
            meta = graph_adapter.get_ingredient_meta(str(ingredient_id))
            return meta
        except RuntimeError as e:
            # Neo4j driver not initialized
            raise ServiceValidationError(
                f"Invalid ingredient {ingredient_id}: Neo4j database not available. {e}"
            )
        except ValueError as e:
            # Ingredient not found in Neo4j
            raise ServiceValidationError(
                f"Invalid ingredient {ingredient_id}: Ingredient not found in catalog. {e}"
            )

    @staticmethod
    def validate_ingredients_batch(
        ingredient_ids: List[uuid.UUID],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Validate multiple ingredients in a single batch query.

        This is more efficient than validating ingredients one by one when
        processing multiple pantry items (e.g., in set_pantry).

        Args:
            ingredient_ids: List of ingredient UUIDs to validate

        Returns:
            Dict mapping ingredient_id (as string) to metadata dict

        Raises:
            ServiceValidationError: If Neo4j is unavailable or any ingredient not found
        """
        if not ingredient_ids:
            return {}

        try:
            # Convert UUIDs to strings for graph adapter
            id_strings = [str(iid) for iid in ingredient_ids]
            meta_map = graph_adapter.get_ingredients_batch(id_strings)
            return meta_map
        except RuntimeError as e:
            # Neo4j driver not initialized
            raise ServiceValidationError(
                f"Cannot validate ingredients: Neo4j database not available. {e}"
            )
        except ValueError as e:
            # One or more ingredients not found
            raise ServiceValidationError(
                f"Cannot validate ingredients: Some ingredients not found in catalog. {e}"
            )

    @staticmethod
    def get_pantry(db: Session, user_id: uuid.UUID) -> List[PantryItem]:
        return db.query(PantryItem).filter(PantryItem.user_id == user_id).all()

    @staticmethod
    def set_pantry(db: Session, user_id: uuid.UUID, items: List[PantryItemCreate]):
        """
        Replace all pantry items for a user with batch ingredient validation.

        This method supports batch-level tracking: multiple entries for the same
        ingredient with different expiry dates are stored separately, allowing
        proper FIFO/FEFO inventory management.

        This method:
        1. Validates user exists
        2. Validates ALL ingredients in one batch query (fail-fast, efficient)
        3. Estimates expiry dates from Neo4j metadata
        4. Atomically deletes old items and inserts new ones
        5. Creates separate rows for items with different best_before dates

        Args:
            db: Database session
            user_id: User's UUID
            items: List of pantry items to set (can include same ingredient
                   with different expiry dates)

        Returns:
            List[PantryItem]: All pantry items for the user after replacement

        Raises:
            NotFoundError: If user not found
            ServiceValidationError: If any ingredient validation fails
        """
        # Verify user exists
        user = db.query(AppUser).filter(AppUser.user_id == user_id).first()
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        # Validate ALL ingredients in batch before making any DB changes
        if items:
            ingredient_ids = [it.ingredient_id for it in items]
            meta_map = PantryService.validate_ingredients_batch(ingredient_ids)
            logger.info(
                f"Validated {len(meta_map)} ingredients in batch for user {user_id}"
            )
        else:
            meta_map = {}

        # Replace all items in a transaction (atomic delete+insert)
        try:
            with db.begin():
                db.query(PantryItem).filter(PantryItem.user_id == user_id).delete()

                for it in items:
                    # Get metadata for this ingredient (already validated above)
                    meta = meta_map.get(str(it.ingredient_id), {})

                    # Estimate expiry from Neo4j metadata if not provided
                    bb = it.best_before
                    if bb is None:
                        shelf_days = meta.get("defaults", {}).get("shelf_life_days")
                        if shelf_days:
                            bb = datetime.utcnow().date() + timedelta(
                                days=int(shelf_days)
                            )
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

            return db.query(PantryItem).filter(PantryItem.user_id == user_id).all()
        except Exception:
            logger.exception("Error setting pantry for user %s", user_id)
            raise

    @staticmethod
    def add_item(db: Session, user_id: uuid.UUID, item: PantryItemCreate):
        """
        Add or update a pantry item for a user with ingredient validation.

        This method:
        1. Validates user exists
        2. Validates ingredient exists in Neo4j (fail-fast, no fake data)
        3. Estimates expiry date from Neo4j metadata if not provided
        4. Upserts pantry item (increment quantity if exists, create if new)

        Args:
            db: Database session
            user_id: User's UUID
            item: Pantry item data to add

        Returns:
            PantryItem: Created or updated pantry item

        Raises:
            NotFoundError: If user not found
            ServiceValidationError: If ingredient validation fails
        """
        # Verify user exists
        user = db.query(AppUser).filter(AppUser.user_id == user_id).first()
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        # Validate ingredient exists in Neo4j and get metadata
        meta = PantryService.validate_ingredient_data(item.ingredient_id)

        # Estimate expiry from Neo4j metadata if not provided
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

        # Perform upsert in a transaction with batch-level granularity
        # Each unique (ingredient, unit, best_before) combination is tracked separately
        try:
            with db.begin():
                try:
                    # Match on best_before to track separate batches with different expiry dates
                    existing = (
                        db.query(PantryItem)
                        .filter(
                            PantryItem.user_id == user_id,
                            PantryItem.ingredient_id == item.ingredient_id,
                            PantryItem.unit == item.unit,
                            PantryItem.best_before
                            == bb,  # Key change: match on expiry date
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
                            PantryItem.best_before == bb,
                        )
                        .first()
                    )

                if existing:
                    # Same batch (same expiry date) - increment quantity
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
                    db.refresh(existing)
                    return existing

                # Different batch (different expiry date) or first entry - create new row
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

        Args:
            db: Database session
            pantry_item_id: UUID of the pantry item to update
            quantity_change: Amount to add (positive) or remove (negative)
            reason: Optional reason for the change (e.g., "cooking", "waste", "found_more")

        Returns:
            PantryItem: Updated pantry item, or None if quantity reaches 0 (auto-deleted)

        Raises:
            NotFoundError: If pantry item not found
            ServiceValidationError: If resulting quantity would be negative
        """
        item = (
            db.query(PantryItem)
            .filter(PantryItem.pantry_item_id == pantry_item_id)
            .first()
        )

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
            # Auto-remove when quantity reaches exactly 0
            logger.info(
                f"Auto-removing pantry item {pantry_item_id} (quantity reached 0). "
                f"Reason: {reason or 'not specified'}"
            )
            db.delete(item)
            db.commit()
            return None

        # Update quantity
        item.quantity = new_qty
        logger.info(
            f"Updated pantry item {pantry_item_id}: "
            f"{current_qty} → {new_qty} (change={change}). "
            f"Reason: {reason or 'not specified'}"
        )

        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def get_expiring_soon(
        db: Session, user_id: uuid.UUID, days_threshold: int = 3
    ) -> List[PantryItem]:
        """
        Get pantry items expiring within the specified number of days.

        This is critical for FIFO/FEFO inventory management and waste prevention.
        Helps users prioritize which ingredients to cook with first.

        Args:
            db: Database session
            user_id: User's UUID
            days_threshold: Number of days ahead to check (default: 3)

        Returns:
            List[PantryItem]: Items expiring soon, ordered by best_before (oldest first)

        Note:
            Items without best_before dates are excluded (can't determine expiry)
        """
        from datetime import date, timedelta

        cutoff_date = date.today() + timedelta(days=days_threshold)

        items = (
            db.query(PantryItem)
            .filter(
                PantryItem.user_id == user_id,
                PantryItem.best_before.isnot(None),  # Only items with expiry dates
                PantryItem.best_before <= cutoff_date,  # Expiring within threshold
            )
            .order_by(PantryItem.best_before.asc())  # Oldest first (FIFO)
            .all()
        )

        logger.info(
            f"Found {len(items)} items expiring within {days_threshold} days "
            f"for user {user_id}"
        )
        return items
