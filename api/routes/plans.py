from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from domain.models import get_db_session
from domain.schemas.plan_schemas import GeneratePlanRequest, PlanEntryResponse, PlanResponse
from services.planner_service import PlanRequest, PlannerService
from app.exceptions import NotFoundError, ServiceValidationError

router = APIRouter(prefix="/plans", tags=["Meal Planning"])
logger = logging.getLogger("smartmeal.api.plans")


@router.post("", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def generate_week_plan(body: GeneratePlanRequest, db: Session = Depends(get_db_session)):
    """
    Generate a personalized weekly meal plan for a user.

    This endpoint:
    1. Fetches user's pantry and allergies from PostgreSQL
    2. Searches for recipe candidates in MongoDB
    3. Checks for conflicts with Neo4j (allergies, dietary restrictions)
    4. Applies substitutions if enabled and conflicts are found
    5. Scores recipes based on pantry match and diversity
    6. Creates a meal plan in PostgreSQL

    Returns:
        PlanResponse with plan_id, week_start (Monday), and number of days
    """
    try:
        service = PlannerService(db)

        # Normalize to Monday
        raw_start = body.week_start or date.today()
        week_monday = raw_start - timedelta(days=raw_start.weekday())

        logger.info(
            "Generating plan for user %s: week_start=%s, days=%d, substitutions=%s",
            body.user_id,
            week_monday,
            body.days,
            body.use_substitutions,
        )

        plan_id = service.generate_plan(
            PlanRequest(
                user_id=body.user_id,
                week_start=week_monday,
                days=body.days,
                use_substitutions=body.use_substitutions,
            )
        )

        return PlanResponse(
            plan_id=plan_id,
            week_start=week_monday,
            days=body.days,
            message="Weekly plan successfully generated.",
        )

    except ValueError as e:
        # User not found, no candidates, etc.
        logger.warning("Validation error generating plan: %s", e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if "not found" in str(e).lower() else status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except NotFoundError as e:
        logger.warning("Resource not found: %s", e)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceValidationError as e:
        logger.warning("Service validation error: %s", e)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error generating weekly plan")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate meal plan: {str(e)}",
        )


@router.get("", response_model=List[PlanResponse])
def list_user_plans(user_id: UUID = Query(..., description="User ID to fetch plans for"), db: Session = Depends(get_db_session)):
    """
    List all meal plans for a specific user.

    Returns a list of plans with their start dates and number of meal entries.
    Plans are ordered by start date (most recent first).
    """
    try:
        service = PlannerService(db)
        plans = service.list_user_plans(user_id)

        logger.info("Found %d plans for user %s", len(plans), user_id)

        return [PlanResponse.model_validate(p) for p in plans]
    except Exception as e:
        logger.exception("Error listing plans for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user plans: {str(e)}",
        )


@router.get("/{plan_id}", response_model=List[PlanEntryResponse])
def get_plan_entries(plan_id: UUID, db: Session = Depends(get_db_session)):
    """
    Get all meal entries for a specific meal plan.

    Returns a list of entries ordered by day_index, each containing:
    - meal_entry_id: Unique entry identifier
    - recipe_id: MongoDB recipe ID
    - day_index: Day number in the plan (0-indexed)
    - servings: Number of servings for this meal
    """
    try:
        service = PlannerService(db)
        entries = service.get_plan_entries(plan_id)

        if not entries:
            logger.warning("Plan %s not found or has no entries", plan_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Meal plan {plan_id} not found or has no entries",
            )

        logger.info("Retrieved %d entries for plan %s", len(entries), plan_id)

        return [PlanEntryResponse.model_validate(e) for e in entries]
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching entries for plan %s", plan_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch plan entries: {str(e)}",
        )