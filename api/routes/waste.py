"""Waste logging and insights routes"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
import logging
from uuid import UUID

from domain.models import get_db_session
from domain.schemas.waste_schemas import (
    WasteLogCreate,
    WasteLogResponse,
    WasteInsightsResponse,
)
from services.waste_service import WasteService

router = APIRouter(prefix="/waste", tags=["Waste Management"])
logger = logging.getLogger("smartmeal.api.waste")


@router.post("", response_model=WasteLogResponse, status_code=status.HTTP_201_CREATED)
def log_waste(
    waste_data: WasteLogCreate,
    user_id: UUID = Query(..., description="User ID to log waste for"),
    db: Session = Depends(get_db_session),
):
    """
    Log a waste entry for a user.
    """
    # Step 1: Validate and normalize waste data
    validated_data = WasteService.validate_waste_data(
        waste_data.ingredient_id, waste_data.quantity, waste_data.unit
    )

    logger.debug(
        f"Waste data validated: ingredient={validated_data.get('ingredient_name')}, "
        f"category={validated_data.get('category')}, "
        f"quantity={validated_data['quantity']}"
    )

    # Step 2: Log the waste (persistence)
    waste_log = WasteService.log_waste(db, user_id, waste_data)

    logger.info(f"Waste logged successfully for user {user_id}: {waste_log.waste_id}")

    return waste_log


@router.get("/insights", response_model=WasteInsightsResponse)
def get_waste_insights(
    user_id: UUID = Query(..., description="User ID to get insights for"),
    horizon: int = Query(
        30, ge=1, le=365, description="Number of days to look back (default: 30)"
    ),
    db: Session = Depends(get_db_session),
):
    """
    Get waste insights for a user over a specified time horizon.
    """
    logger.info(f"Fetching waste insights for user {user_id}, horizon={horizon} days")

    insights = WasteService.build_insights(db, user_id, horizon)

    logger.info(
        f"Waste insights generated for user {user_id}: "
        f"{insights.total_waste_count} logs, "
        f"{len(insights.most_wasted_ingredients)} ingredients"
    )

    return insights
