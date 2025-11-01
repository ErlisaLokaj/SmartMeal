"""Profile management routes (dietary profile, allergies, preferences)"""

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
import json
import logging
from uuid import UUID
from typing import List

from domain.models import get_db_session, AppUser
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
from services import ProfileService
from core.exceptions import ServiceValidationError, NotFoundError

router = APIRouter(prefix="/profiles", tags=["Profiles"])
logger = logging.getLogger("smartmeal.api.profiles")


def get_db():
    """Database session dependency"""
    yield from get_db_session()


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


@router.get("/{user_id}", response_model=UserProfileResponse)
def get_profile(user_id: UUID, db: Session = Depends(get_db)):
    """Get complete user profile including dietary settings, allergies, and preferences."""
    user = ProfileService.get_user_profile(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found"
        )

    return _user_to_response(user)


@router.put("/{user_id}", response_model=UserProfileResponse)
def update_profile(
    user_id: UUID, profile_data: ProfileUpdateRequest, db: Session = Depends(get_db)
):
    """
    Update user profile, dietary settings, allergies, and preferences.
    This endpoint implements the complete sequence diagram flow.
    """
    try:
        user, created = ProfileService.upsert_profile(db, user_id, profile_data)
        resp = _user_to_response(user)
        if created:
            headers = {"Location": f"/profiles/{user.user_id}"}
            return Response(
                content=resp.model_dump_json(),
                status_code=status.HTTP_201_CREATED,
                media_type="application/json",
                headers=headers,
            )
        return resp
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error updating profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# Dietary Profile endpoints
@router.get("/{user_id}/dietary", response_model=DietaryProfileResponse)
def get_dietary_profile(user_id: UUID, db: Session = Depends(get_db)):
    """Get user's dietary profile"""
    dietary = ProfileService.get_dietary_profile(db, user_id)
    if not dietary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dietary profile not found for user {user_id}",
        )

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
    user_id: UUID, profile_data: DietaryProfileCreate, db: Session = Depends(get_db)
):
    """Set or update user's dietary profile"""
    try:
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
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# Preferences endpoints
@router.get("/{user_id}/preferences", response_model=List[PreferenceResponse])
def get_preferences(user_id: UUID, db: Session = Depends(get_db)):
    """Get user's preferences"""
    preferences = ProfileService.get_preferences(db, user_id)
    return [PreferenceResponse.model_validate(p) for p in preferences]


@router.put("/{user_id}/preferences", response_model=List[PreferenceResponse])
def set_preferences(
    user_id: UUID, preferences: List[PreferenceCreate], db: Session = Depends(get_db)
):
    """Replace all user preferences"""
    try:
        prefs = ProfileService.set_preferences(db, user_id, preferences)
        return [PreferenceResponse.model_validate(p) for p in prefs]
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{user_id}/preferences",
    response_model=PreferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_preference(
    user_id: UUID, preference: PreferenceCreate, db: Session = Depends(get_db)
):
    """Add a single preference"""
    try:
        pref = ProfileService.add_preference(db, user_id, preference)
        return PreferenceResponse.model_validate(pref)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{user_id}/preferences/{tag}")
def remove_preference(user_id: UUID, tag: str, db: Session = Depends(get_db)):
    """Remove a preference by tag"""
    success = ProfileService.remove_preference(db, user_id, tag)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preference '{tag}' not found for user {user_id}",
        )
    return {"status": "ok", "deleted": tag}


# Allergies endpoints
@router.get("/{user_id}/allergies", response_model=List[AllergyResponse])
def get_allergies(user_id: UUID, db: Session = Depends(get_db)):
    """Get user's allergies"""
    allergies = ProfileService.get_allergies(db, user_id)
    return [AllergyResponse.model_validate(a) for a in allergies]


@router.put("/{user_id}/allergies", response_model=List[AllergyResponse])
def set_allergies(
    user_id: UUID, allergies: List[AllergyCreate], db: Session = Depends(get_db)
):
    """Replace all user allergies"""
    try:
        alls = ProfileService.set_allergies(db, user_id, allergies)
        return [AllergyResponse.model_validate(a) for a in alls]
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{user_id}/allergies",
    response_model=AllergyResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_allergy(user_id: UUID, allergy: AllergyCreate, db: Session = Depends(get_db)):
    """Add a single allergy"""
    try:
        a = ProfileService.add_allergy(db, user_id, allergy)
        return AllergyResponse.model_validate(a)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ServiceValidationError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{user_id}/allergies/{ingredient_id}")
def remove_allergy(user_id: UUID, ingredient_id: UUID, db: Session = Depends(get_db)):
    """Remove an allergy by ingredient_id"""
    success = ProfileService.remove_allergy(db, user_id, ingredient_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Allergy for ingredient {ingredient_id} not found for user {user_id}",
        )
    return {"status": "ok", "deleted": str(ingredient_id)}
