"""
Save-me-first API routes - Food waste prevention suggestions.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import logging

from api.dependencies import get_db
from api.responses import success_response, error_response
from domain.schemas.save_me_first_schemas import SaveMeFirstResponse
from services.save_me_first_service import SaveMeFirstService
from app.exceptions import NotFoundError, ServiceValidationError

router = APIRouter(prefix="/save-me-first", tags=["save-me-first"])
logger = logging.getLogger("smartmeal.api.save_me_first")


@router.get("", response_model=dict)
def get_save_me_first_suggestions(
    days_threshold: int = Query(
        default=3,
        ge=1,
        le=14,
        description="Days before expiry to consider items (1–14 days)",
    ),
    max_suggestions: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of recipe suggestions (1–20)",
    ),
    db: Session = Depends(get_db)
):
    """
    **Get save-me-first suggestions to prevent food waste.**

    This endpoint helps users reduce food waste by:
    1. Identifying pantry items expiring soon
    2. Suggesting recipes that use these ingredients
    3. Prioritizing by urgency and match score
    4. Providing actionable waste prevention tips
    """
    try:
        logger.info(
            f"Generating save-me-first suggestions "
            f"(threshold: {days_threshold} days, max: {max_suggestions})"
        )

        # For now, call without user_id since auth not implemented
        response = SaveMeFirstService.generate_suggestions(
            db=db,
            user_id=None,
            days_threshold=days_threshold,
            max_suggestions=max_suggestions,
        )

        return success_response(
            data=response.model_dump(),
            message=(
                f"Found {response.total_expiring} expiring items "
                f"({response.critical_count} critical, "
                f"{response.urgent_count} urgent)"
            ),
        )

    except NotFoundError as e:
        logger.warning(f"Not found error: {e}")
        return error_response(str(e), 404)
    except ServiceValidationError as e:
        logger.warning(f"Validation error: {e}")
        return error_response(str(e), 400)
    except Exception as e:
        logger.error(f"Error generating save-me-first suggestions: {e}", exc_info=True)
        return error_response("Failed to generate save-me-first suggestions", 500)
