from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, case
import logging
import uuid
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta

from domain.models import WasteLog, AppUser
from domain.schemas.waste_schemas import (
    WasteLogCreate,
    WasteLogResponse,
    WasteInsightsResponse,
    WasteByIngredient,
    WasteByCategory,
    WasteTrend,
)
from adapters import graph_adapter
from core.exceptions import NotFoundError, ServiceValidationError

logger = logging.getLogger("smartmeal.waste")


class WasteService:
    @staticmethod
    def validate_waste_data(
        ingredient_id: uuid.UUID, quantity: Decimal, unit: str = None
    ) -> Dict[str, Any]:
        """
        PUBLIC validation method - validates waste data before logging.
        This is a separate step as shown in the sequence diagram.

        Validates and normalizes waste log data, enriches with ingredient metadata.

        Args:
            ingredient_id: UUID of the ingredient
            quantity: Quantity of wasted ingredient
            unit: Unit of measurement

        Returns:
            Dict with validated and enriched data including:
            - ingredient_id
            - quantity
            - unit (normalized)
            - ingredient_name (from Neo4j)
            - category (from Neo4j)

        Raises:
            ServiceValidationError: If validation fails or ingredient not found
        """
        try:
            # Validate quantity
            if quantity <= 0:
                raise ServiceValidationError("Quantity must be greater than 0")

            # Normalize unit (convert to lowercase, trim whitespace)
            normalized_unit = unit.lower().strip() if unit else None

            # Fetch ingredient metadata from Neo4j to:
            # 1. Validate ingredient exists
            # 2. Enrich waste log with name and category for better insights
            try:
                meta = graph_adapter.get_ingredient_meta(str(ingredient_id))
                ingredient_name = meta.get("name", "Unknown")
                category = meta.get("category", "unknown")
                logger.debug(
                    f"Ingredient metadata fetched: id={ingredient_id}, "
                    f"name={ingredient_name}, category={category}"
                )
            except (RuntimeError, ValueError) as e:
                # Neo4j unavailable or ingredient not found
                logger.error(f"Failed to fetch ingredient metadata: {e}")
                raise ServiceValidationError(f"Invalid ingredient: {str(e)}") from e

            return {
                "ingredient_id": ingredient_id,
                "quantity": quantity,
                "unit": normalized_unit,
                "ingredient_name": ingredient_name,
                "category": category,
            }
        except ServiceValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating waste data: {e}")
            raise ServiceValidationError(f"Invalid waste data: {str(e)}")

    @staticmethod
    def validate_normalize(
        ingredient_id: uuid.UUID, quantity: Decimal, unit: str = None
    ) -> Dict[str, Any]:
        """
        DEPRECATED: Use validate_waste_data() instead.
        Kept for backward compatibility.
        """
        return WasteService.validate_waste_data(ingredient_id, quantity, unit)

    @staticmethod
    def log_waste(
        db: Session, user_id: uuid.UUID, waste_data: WasteLogCreate
    ) -> WasteLogResponse:
        """
        Log a waste entry for a user with optional pantry integration.

        If pantry_item_id and auto_remove_from_pantry are provided, this will
        automatically update or remove the item from the user's pantry, ensuring
        consistency between waste logs and actual pantry inventory.

        Note: Validation should be performed separately using validate_waste_data()
        before calling this method (as per sequence diagram).

        Args:
            db: Database session
            user_id: UUID of the user
            waste_data: Waste log data (should already be validated)
                - If pantry_item_id provided: Links waste to specific pantry item
                - If auto_remove_from_pantry=True: Updates pantry automatically

        Returns:
            WasteLogResponse with created waste log

        Raises:
            NotFoundError: If user not found or pantry_item not found (if specified)
            ServiceValidationError: If validation fails or pantry update fails
        """
        from services.pantry_service import PantryService
        from decimal import Decimal

        # Verify user exists
        user = db.query(AppUser).filter(AppUser.user_id == user_id).first()
        if not user:
            logger.warning(f"log_waste failed: user {user_id} not found")
            raise NotFoundError(f"User {user_id} not found")

        # For safety, still validate here (defense in depth)
        validated = WasteService.validate_waste_data(
            waste_data.ingredient_id, waste_data.quantity, waste_data.unit
        )

        # Pantry integration: Update/remove from pantry if requested
        pantry_updated = False
        if waste_data.auto_remove_from_pantry and waste_data.pantry_item_id:
            try:
                # Attempt to decrement quantity from pantry
                updated_item = PantryService.update_quantity(
                    db,
                    waste_data.pantry_item_id,
                    -Decimal(str(waste_data.quantity)),  # Negative = remove
                    reason=f"waste: {waste_data.reason or 'unspecified'}",
                )
                if updated_item is None:
                    logger.info(
                        f"Pantry item {waste_data.pantry_item_id} auto-removed "
                        f"(quantity reached 0) when logging waste"
                    )
                else:
                    logger.info(
                        f"Pantry item {waste_data.pantry_item_id} quantity decremented "
                        f"by {waste_data.quantity} when logging waste"
                    )
                pantry_updated = True
            except NotFoundError:
                logger.warning(
                    f"Could not update pantry: item {waste_data.pantry_item_id} not found. "
                    "Continuing with waste log creation."
                )
                # Don't fail the waste logging - just log the warning
            except ServiceValidationError as e:
                logger.warning(
                    f"Could not update pantry for waste log: {e}. "
                    "Continuing with waste log creation."
                )
                # Don't fail - user might be logging waste of item already consumed

        # Create waste log entry
        waste_log = WasteLog(
            user_id=user_id,
            ingredient_id=validated["ingredient_id"],
            quantity=validated["quantity"],
            unit=validated["unit"],
            reason=waste_data.reason,
        )

        db.add(waste_log)
        db.commit()
        db.refresh(waste_log)

        logger.info(
            f"waste_logged user_id={user_id} waste_id={waste_log.waste_id} "
            f"ingredient={validated.get('ingredient_name', 'unknown')} "
            f"quantity={validated['quantity']} unit={validated.get('unit', 'N/A')} "
            f"reason={waste_data.reason or 'unspecified'} "
            f"pantry_updated={pantry_updated}"
        )

        return WasteLogResponse.model_validate(waste_log)

    @staticmethod
    def build_insights(
        db: Session, user_id: uuid.UUID, horizon_days: int = 30
    ) -> WasteInsightsResponse:
        """
        Build waste insights for a user over a specified time horizon.

        Uses batch Neo4j queries to avoid N+1 problem and improve performance.

        Args:
            db: Database session
            user_id: UUID of the user
            horizon_days: Number of days to look back (default: 30)

        Returns:
            WasteInsightsResponse with aggregated insights

        Raises:
            NotFoundError: If user not found
        """
        # Verify user exists
        user = db.query(AppUser).filter(AppUser.user_id == user_id).first()
        if not user:
            logger.warning(f"build_insights failed: user {user_id} not found")
            raise NotFoundError(f"User {user_id} not found")

        # Calculate the date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=horizon_days)

        logger.info(
            f"build_insights user_id={user_id} horizon={horizon_days}d "
            f"date_range={start_date.date()} to {end_date.date()}"
        )

        # Get all waste logs within the horizon
        waste_logs = (
            db.query(WasteLog)
            .filter(WasteLog.user_id == user_id, WasteLog.occurred_at >= start_date)
            .all()
        )

        if not waste_logs:
            logger.info(
                f"No waste logs found for user {user_id} in the last {horizon_days} days"
            )
            # Return empty insights if no waste logs
            return WasteInsightsResponse(
                total_waste_count=0,
                total_quantity=Decimal("0"),
                most_wasted_ingredients=[],
                waste_by_category=[],
                waste_trends=[],
                common_reasons=[],
                horizon_days=horizon_days,
            )

        # Calculate total metrics
        total_waste_count = len(waste_logs)
        total_quantity = sum(log.quantity for log in waste_logs)

        logger.info(
            f"Found {total_waste_count} waste logs with total quantity {total_quantity}"
        )

        unique_ingredient_ids = list(set(str(log.ingredient_id) for log in waste_logs))
        logger.debug(
            f"Fetching metadata for {len(unique_ingredient_ids)} unique ingredients"
        )

        try:
            ingredient_metadata_map = graph_adapter.get_ingredients_batch(
                unique_ingredient_ids
            )
            logger.info(
                f"Fetched metadata for {len(ingredient_metadata_map)} ingredients from Neo4j"
            )
        except (RuntimeError, ValueError) as e:
            logger.error(f"Failed to fetch ingredient metadata from Neo4j: {e}")
            raise ServiceValidationError(
                f"Cannot build insights: Neo4j error - {str(e)}"
            ) from e

        # Aggregate by ingredient
        ingredient_aggregates = {}
        for log in waste_logs:
            key = str(log.ingredient_id)
            if key not in ingredient_aggregates:
                # Get metadata from batch-fetched map
                meta = ingredient_metadata_map.get(key, {})
                ingredient_aggregates[key] = {
                    "ingredient_id": log.ingredient_id,
                    "ingredient_name": meta.get("name", "Unknown"),
                    "total_quantity": Decimal("0"),
                    "waste_count": 0,
                    "unit": log.unit,
                }
            ingredient_aggregates[key]["total_quantity"] += log.quantity
            ingredient_aggregates[key]["waste_count"] += 1

        # Sort by total quantity and get top ingredients
        most_wasted = sorted(
            ingredient_aggregates.values(),
            key=lambda x: x["total_quantity"],
            reverse=True,
        )[:10]

        most_wasted_ingredients = []
        for item in most_wasted:
            percentage = (
                float(item["total_quantity"] / total_quantity * 100)
                if total_quantity > 0
                else 0
            )
            most_wasted_ingredients.append(
                WasteByIngredient(
                    ingredient_id=item["ingredient_id"],
                    ingredient_name=item["ingredient_name"],
                    total_quantity=item["total_quantity"],
                    unit=item["unit"],
                    waste_count=item["waste_count"],
                    percentage_of_total=round(percentage, 2),
                )
            )

        # Aggregate by category (from batch-fetched metadata)
        category_aggregates = {}
        for log in waste_logs:
            meta = ingredient_metadata_map.get(str(log.ingredient_id), {})
            category = meta.get("category", "unknown")

            if category not in category_aggregates:
                category_aggregates[category] = {
                    "total_quantity": Decimal("0"),
                    "waste_count": 0,
                }
            category_aggregates[category]["total_quantity"] += log.quantity
            category_aggregates[category]["waste_count"] += 1

        waste_by_category = []
        for category, data in sorted(
            category_aggregates.items(),
            key=lambda x: x[1]["total_quantity"],
            reverse=True,
        ):
            percentage = (
                float(data["total_quantity"] / total_quantity * 100)
                if total_quantity > 0
                else 0
            )
            waste_by_category.append(
                WasteByCategory(
                    category=category,
                    total_quantity=data["total_quantity"],
                    waste_count=data["waste_count"],
                    percentage_of_total=round(percentage, 2),
                )
            )

        # Calculate trends by week
        trend_aggregates = {}
        for log in waste_logs:
            # Group by week (ISO week format: YYYY-Www)
            week_key = log.occurred_at.strftime("%Y-W%U")
            if week_key not in trend_aggregates:
                trend_aggregates[week_key] = {
                    "total_quantity": Decimal("0"),
                    "waste_count": 0,
                }
            trend_aggregates[week_key]["total_quantity"] += log.quantity
            trend_aggregates[week_key]["waste_count"] += 1

        waste_trends = [
            WasteTrend(
                period=period,
                total_quantity=data["total_quantity"],
                waste_count=data["waste_count"],
            )
            for period, data in sorted(trend_aggregates.items())
        ]

        # Aggregate by reason
        reason_aggregates = {}
        for log in waste_logs:
            reason = log.reason or "unspecified"
            reason_aggregates[reason] = reason_aggregates.get(reason, 0) + 1

        common_reasons = [
            {"reason": reason, "count": count}
            for reason, count in sorted(
                reason_aggregates.items(), key=lambda x: x[1], reverse=True
            )[:5]
        ]

        logger.info(
            f"build_insights completed: user_id={user_id} "
            f"total_count={total_waste_count} "
            f"categories={len(waste_by_category)} "
            f"trends={len(waste_trends)} "
            f"top_reasons={len(common_reasons)}"
        )

        return WasteInsightsResponse(
            total_waste_count=total_waste_count,
            total_quantity=total_quantity,
            most_wasted_ingredients=most_wasted_ingredients,
            waste_by_category=waste_by_category,
            waste_trends=waste_trends,
            common_reasons=common_reasons,
            horizon_days=horizon_days,
        )
