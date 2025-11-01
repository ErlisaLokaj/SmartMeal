"""User management routes"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import json
import logging
from uuid import UUID
from typing import List

from domain.models import get_db_session, AppUser
from domain.schemas.profile_schemas import (
    UserProfileResponse,
    UserCreate,
    DietaryProfileResponse,
    AllergyResponse,
    PreferenceResponse,
)
from services import ProfileService
from core.exceptions import ServiceValidationError, NotFoundError

router = APIRouter(prefix="/users", tags=["Users"])
logger = logging.getLogger("smartmeal.api.users")


def _user_to_response(user: AppUser) -> UserProfileResponse:
    """Helper: map AppUser (ORM) to UserProfileResponse"""
    dietary_response = None
    if user.dietary_profile:
        dp = user.dietary_profile
        dietary_response = DietaryProfileResponse(
            goal=dp.goal,
            activity=dp.activity,
            kcal_target=dp.kcal_target,
            protein_target_g=dp.protein_target_g,
            carb_target_g=dp.carb_target_g,
            fat_target_g=dp.fat_target_g,
            cuisine_likes=json.loads(dp.cuisine_likes) if dp.cuisine_likes else [],
            cuisine_dislikes=(
                json.loads(dp.cuisine_dislikes) if dp.cuisine_dislikes else []
            ),
            updated_at=dp.updated_at,
        )

    return UserProfileResponse(
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        created_at=user.created_at,
        updated_at=user.updated_at,
        dietary_profile=dietary_response,
        allergies=[AllergyResponse.model_validate(a) for a in user.allergies],
        preferences=[PreferenceResponse.model_validate(p) for p in user.preferences],
    )


def get_db():
    """Database session dependency"""
    yield from get_db_session()


@router.post(
    "", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED
)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user from JSON body"""
    try:
        new_user = ProfileService.create_user(db, user.email, user.full_name)
        return _user_to_response(new_user)
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error creating user: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("", response_model=List[UserProfileResponse])
def get_all_users(db: Session = Depends(get_db)):
    """Return all users (summary/full profile)."""
    users = ProfileService.get_all_users(db)
    return [_user_to_response(u) for u in users]


@router.get("/{user_id}", response_model=UserProfileResponse)
def get_user(user_id: UUID, db: Session = Depends(get_db)):
    """Get complete user profile including dietary settings, allergies, and preferences."""
    user = ProfileService.get_user_profile(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found"
        )

    return _user_to_response(user)


@router.delete("/{user_id}")
def delete_user(user_id: UUID, db: Session = Depends(get_db)):
    """Delete a user and all their related data."""
    success = ProfileService.delete_user(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found"
        )
    return {"status": "ok", "deleted": str(user_id)}
