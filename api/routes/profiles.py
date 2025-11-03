"""Profile management routes (dietary profile, allergies, preferences)"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session
import json
import logging
from uuid import UUID
from typing import List

from domain.models import get_db_session
from domain.schemas.profile_schemas import (
    UserProfileResponse,
    ProfileUpdateRequest,
    DietaryProfileResponse,
    DietaryProfileCreate,
    AllergyResponse,
    AllergyCreate,
    PreferenceResponse,
    PreferenceCreate,
)
from services.profile_service import ProfileService
from app.exceptions import NotFoundError
from domain.mappers import UserMapper

router = APIRouter(prefix="/profiles", tags=["Profiles"])
logger = logging.getLogger("smartmeal.api.profiles")


@router.get("/{user_id}", response_model=UserProfileResponse)
def get_profile(user_id: UUID, db: Session = Depends(get_db_session)):
    """Get complete user profile including dietary settings, allergies, and preferences."""
    user = ProfileService.get_user_profile(db, user_id)
    if not user:
        raise NotFoundError(f"User {user_id} not found")
    return UserMapper.to_response(user)


@router.put("/{user_id}", response_model=UserProfileResponse)
def update_profile(
    user_id: UUID,
    profile_data: ProfileUpdateRequest,
    db: Session = Depends(get_db_session),
):
    """
    Update user profile, dietary settings, allergies, and preferences.
    This endpoint implements the complete sequence diagram flow.
    """
    user, created = ProfileService.upsert_profile(db, user_id, profile_data)
    resp = UserMapper.to_response(user)
    if created:
        headers = {"Location": f"/profiles/{user.user_id}"}
        return Response(
            content=resp.model_dump_json(),
            status_code=status.HTTP_201_CREATED,
            media_type="application/json",
            headers=headers,
        )
    return resp


# Dietary Profile endpoints
@router.get("/{user_id}/dietary", response_model=DietaryProfileResponse)
def get_dietary_profile(user_id: UUID, db: Session = Depends(get_db_session)):
    """Get user's dietary profile"""
    dietary = ProfileService.get_dietary_profile(db, user_id)
    if not dietary:
        raise NotFoundError(f"Dietary profile not found for user {user_id}")

    return DietaryProfileResponse(
        goal=dietary.goal,
        activity=dietary.activity,
        kcal_target=dietary.kcal_target,
        protein_target_g=dietary.protein_target_g,
        carb_target_g=dietary.carb_target_g,
        fat_target_g=dietary.fat_target_g,
        cuisine_likes=(
            json.loads(dietary.cuisine_likes) if dietary.cuisine_likes else []
        ),
        cuisine_dislikes=(
            json.loads(dietary.cuisine_dislikes) if dietary.cuisine_dislikes else []
        ),
        updated_at=dietary.updated_at,
    )


@router.put("/{user_id}/dietary", response_model=DietaryProfileResponse)
def set_dietary_profile(
    user_id: UUID,
    profile_data: DietaryProfileCreate,
    db: Session = Depends(get_db_session),
):
    """Set or update user's dietary profile"""
    dietary = ProfileService.set_dietary_profile(db, user_id, profile_data)
    return DietaryProfileResponse(
        goal=dietary.goal,
        activity=dietary.activity,
        kcal_target=dietary.kcal_target,
        protein_target_g=dietary.protein_target_g,
        carb_target_g=dietary.carb_target_g,
        fat_target_g=dietary.fat_target_g,
        cuisine_likes=(
            json.loads(dietary.cuisine_likes) if dietary.cuisine_likes else []
        ),
        cuisine_dislikes=(
            json.loads(dietary.cuisine_dislikes) if dietary.cuisine_dislikes else []
        ),
        updated_at=dietary.updated_at,
    )


# Preferences endpoints
@router.get("/{user_id}/preferences", response_model=List[PreferenceResponse])
def get_preferences(user_id: UUID, db: Session = Depends(get_db_session)):
    """Get user's preferences"""
    preferences = ProfileService.get_preferences(db, user_id)
    return [PreferenceResponse.model_validate(p) for p in preferences]


@router.put("/{user_id}/preferences", response_model=List[PreferenceResponse])
def set_preferences(
    user_id: UUID,
    preferences: List[PreferenceCreate],
    db: Session = Depends(get_db_session),
):
    """Replace all user preferences"""
    prefs = ProfileService.set_preferences(db, user_id, preferences)
    return [PreferenceResponse.model_validate(p) for p in prefs]


@router.post(
    "/{user_id}/preferences",
    response_model=PreferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_preference(
    user_id: UUID, preference: PreferenceCreate, db: Session = Depends(get_db_session)
):
    """Add a single preference"""
    pref = ProfileService.add_preference(db, user_id, preference)
    return PreferenceResponse.model_validate(pref)


@router.delete("/{user_id}/preferences/{tag}")
def remove_preference(user_id: UUID, tag: str, db: Session = Depends(get_db_session)):
    """Remove a preference by tag"""
    success = ProfileService.remove_preference(db, user_id, tag)
    if not success:
        raise NotFoundError(f"Preference '{tag}' not found for user {user_id}")
    return {"status": "ok", "deleted": tag}


# Allergies endpoints
@router.get("/{user_id}/allergies", response_model=List[AllergyResponse])
def get_allergies(user_id: UUID, db: Session = Depends(get_db_session)):
    """Get user's allergies"""
    allergies = ProfileService.get_allergies(db, user_id)
    return [AllergyResponse.model_validate(a) for a in allergies]


@router.put("/{user_id}/allergies", response_model=List[AllergyResponse])
def set_allergies(
    user_id: UUID, allergies: List[AllergyCreate], db: Session = Depends(get_db_session)
):
    """Replace all user allergies"""
    alls = ProfileService.set_allergies(db, user_id, allergies)
    return [AllergyResponse.model_validate(a) for a in alls]


@router.post(
    "/{user_id}/allergies",
    response_model=AllergyResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_allergy(
    user_id: UUID, allergy: AllergyCreate, db: Session = Depends(get_db_session)
):
    """Add a single allergy"""
    a = ProfileService.add_allergy(db, user_id, allergy)
    return AllergyResponse.model_validate(a)


@router.delete("/{user_id}/allergies/{ingredient_id}")
def remove_allergy(
    user_id: UUID, ingredient_id: UUID, db: Session = Depends(get_db_session)
):
    """Remove an allergy by ingredient_id"""
    success = ProfileService.remove_allergy(db, user_id, ingredient_id)
    if not success:
        raise NotFoundError(
            f"Allergy for ingredient {ingredient_id} not found for user {user_id}"
        )
    return {"status": "ok", "deleted": str(ingredient_id)}
