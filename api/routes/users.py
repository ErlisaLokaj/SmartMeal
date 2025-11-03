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
from services.profile_service import ProfileService
from app.exceptions import ServiceValidationError, NotFoundError
from domain.mappers import UserMapper

router = APIRouter(prefix="/users", tags=["Users"])
logger = logging.getLogger("smartmeal.api.users")


@router.post(
    "", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED
)
def create_user(user: UserCreate, db: Session = Depends(get_db_session)):
    """Create a new user from JSON body"""
    new_user = ProfileService.create_user(db, user.email, user.full_name)
    return UserMapper.to_response(new_user)


@router.get("", response_model=List[UserProfileResponse])
def get_all_users(db: Session = Depends(get_db_session)):
    """Return all users (summary/full profile)."""
    users = ProfileService.get_all_users(db)
    return [UserMapper.to_response(u) for u in users]


@router.get("/{user_id}", response_model=UserProfileResponse)
def get_user(user_id: UUID, db: Session = Depends(get_db_session)):
    """Get complete user profile including dietary settings, allergies, and preferences."""
    user = ProfileService.get_user_profile(db, user_id)
    if not user:
        raise NotFoundError(f"User {user_id} not found")
    return UserMapper.to_response(user)


@router.delete("/{user_id}")
def delete_user(user_id: UUID, db: Session = Depends(get_db_session)):
    """Delete a user and all their related data."""
    success = ProfileService.delete_user(db, user_id)
    if not success:
        raise NotFoundError(f"User {user_id} not found")
    return {"status": "ok", "deleted": str(user_id)}
