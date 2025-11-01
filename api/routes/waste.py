"""Waste logging and insights routes"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging
from uuid import UUID

from domain.models import get_db_session
from domain.schemas.waste_schemas import (
    WasteLogCreate,
    WasteLogResponse,
    WasteInsightsResponse,
)
from services import WasteService
from core.exceptions import ServiceValidationError, NotFoundError

router = APIRouter(prefix="/waste", tags=["Waste Management"])
logger = logging.getLogger("smartmeal.api.waste")


def get_db():
    """Database session dependency"""
    yield from get_db_session()


@router.post("", response_model=WasteLogResponse, status_code=status.HTTP_201_CREATED)
def log_waste(
    waste_data: WasteLogCreate,
    user_id: UUID = Query(..., description="User ID to log waste for"),
    db: Session = Depends(get_db),
):
    """
    Log a waste entry for a user.

    This endpoint implements the improved waste logging flow from the sequence diagram:
    1. Validate schema with Pydantic (automatic)
    2. Validate and normalize waste data (separate step)
    3. Enrich with ingredient metadata from Neo4j
    4. Verify user exists
    5. Insert waste log into PostgreSQL
    6. Return saved waste log

    Args:
        waste_data: Waste log data (ingredient_id, quantity, unit, reason)
        user_id: UUID of the user logging the waste
        db: Database session (injected)

    Returns:
        WasteLogResponse with the created waste log

    Raises:
        400: If validation fails
        404: If user not found
        500: Internal server error
    """
    try:
        # Step 1: Validate and normalize waste data (separate from persistence)
        # This enriches the data with ingredient name and category from Neo4j
        validated_data = WasteService.validate_waste_data(
            waste_data.ingredient_id,
            waste_data.quantity,
            waste_data.unit
        )
        
        logger.debug(
            f"Waste data validated: ingredient={validated_data.get('ingredient_name')}, "
            f"category={validated_data.get('category')}, "
            f"quantity={validated_data['quantity']}"
        )
        
        # Step 2: Log the waste (persistence)
        waste_log = WasteService.log_waste(db, user_id, waste_data)
        
        logger.info(
            f"Waste logged successfully for user {user_id}: {waste_log.waste_id}"
        )
        
        return waste_log
        
    except NotFoundError as e:
        logger.warning(f"User not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceValidationError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error logging waste: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/insights", response_model=WasteInsightsResponse)
def get_waste_insights(
    user_id: UUID = Query(..., description="User ID to get insights for"),
    horizon: int = Query(
        30, ge=1, le=365, description="Number of days to look back (default: 30)"
    ),
    db: Session = Depends(get_db),
):
    """
    Get waste insights for a user over a specified time horizon.

    This endpoint implements the improved insights flow from the sequence diagram:
    1. Verify user exists
    2. Query PostgreSQL for waste logs within horizon
    3. Extract unique ingredient IDs
    4. Batch fetch ingredient metadata from Neo4j (optimized - no N+1 problem)
    5. Aggregate totals, by ingredient, by category, trends, reasons
    6. Calculate percentages
    7. Return comprehensive insights

    Args:
        user_id: UUID of the user
        horizon: Number of days to look back (default: 30, max: 365)
        db: Database session (injected)

    Returns:
        WasteInsightsResponse with comprehensive waste insights including:
        - Total waste count and quantity
        - Most wasted ingredients (with names from Neo4j)
        - Waste by category (from Neo4j metadata)
        - Waste trends over time (by week)
        - Common waste reasons (top 5)

    Raises:
        404: If user not found
        500: Internal server error
    """
    try:
        logger.info(f"Fetching waste insights for user {user_id}, horizon={horizon} days")
        
        insights = WasteService.build_insights(db, user_id, horizon)
        
        logger.info(
            f"Waste insights generated for user {user_id}: "
            f"{insights.total_waste_count} logs, "
            f"{len(insights.most_wasted_ingredients)} ingredients, "
            f"{len(insights.waste_by_category)} categories"
        )
        
        return insights
        
    except NotFoundError as e:
        logger.warning(f"User not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error fetching waste insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

