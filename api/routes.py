from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import json
import logging
from uuid import UUID
from typing import List, Optional

from core.database.models import get_db, AppUser
from core.schemas.profile_schemas import *
from core.services.profile_service import ProfileService
from core.services.pantry_service import PantryService
from core.schemas.profile_schemas import (
    PantryItemResponse,
    PantryItemCreate,
    PantryItemCreateRequest,
)
from core.services.recommendation_service import RecommendationService
from core.schemas.recipe_schemas import RecipeRecommendation, RecommendationRequest

router = APIRouter(prefix="", tags=["SmartMeal"])

logger = logging.getLogger("smartmeal.api.routes")


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


@router.get("/users/{user_id}", response_model=UserProfileResponse)
def get_profile(user_id: UUID, db: Session = Depends(get_db)):
    """
    Get complete user profile including dietary settings, allergies, and preferences.
    """
    user = ProfileService.get_user_profile(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found"
        )

    return _user_to_response(user)


@router.put("/users/{user_id}", response_model=UserProfileResponse)
def update_profile(
    user_id: UUID, profile_data: ProfileUpdateRequest, db: Session = Depends(get_db)
):
    """
    Update user profile, dietary settings, allergies, and preferences.
    This endpoint implements the complete sequence diagram flow.
    """
    try:
        user = ProfileService.upsert_profile(db, user_id, profile_data)
        return _user_to_response(user)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error updating profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/users", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED
)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user from JSON body"""
    try:
        new_user = ProfileService.create_user(db, user.email, user.full_name)
        return _user_to_response(new_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/users", response_model=List[UserProfileResponse])
def get_all_users(db: Session = Depends(get_db)):
    """Return all users (summary/full profile)."""
    users = ProfileService.get_all_users(db)
    return [_user_to_response(u) for u in users]


@router.delete("/users/{user_id}")
def delete_user(user_id: UUID, db: Session = Depends(get_db)):
    """Delete a user and all their related data."""
    success = ProfileService.delete_user(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found"
        )
    return {"status": "ok", "deleted": str(user_id)}


@router.get("/health-check")
def health_check():
    return {"status": "ok", "service": "SmartMeal"}


@router.put("/pantry", response_model=List[PantryItemResponse])
def update_pantry(pantry: PantryUpdateRequest, db: Session = Depends(get_db)):
    try:
        items = PantryService.set_pantry(db, pantry.user_id, pantry.items)
        return [PantryItemResponse.model_validate(i) for i in items]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/pantry", response_model=List[PantryItemResponse])
def get_pantry(user_id: UUID = Query(...), db: Session = Depends(get_db)):
    items = PantryService.get_pantry(db, user_id)
    return [PantryItemResponse.model_validate(i) for i in items]


@router.post(
    "/pantry", response_model=PantryItemResponse, status_code=status.HTTP_201_CREATED
)
def add_pantry_item(payload: PantryItemCreateRequest, db: Session = Depends(get_db)):
    """Add a single pantry item for user (provide user_id in request body)."""
    try:
        p = PantryService.add_item(db, payload.user_id, payload.item)
        return PantryItemResponse.model_validate(p)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/pantry/{pantry_item_id}")
def delete_pantry_item(pantry_item_id: UUID, db: Session = Depends(get_db)):
    success = PantryService.remove_item(db, pantry_item_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pantry item {pantry_item_id} not found",
        )
    return {"status": "ok", "removed": str(pantry_item_id)}


@router.get("/users/{user_id}/dietary", response_model=DietaryProfileResponse)
def get_dietary_profile(user_id: UUID, db: Session = Depends(get_db)):
    dp = ProfileService.get_dietary_profile(db, user_id)
    if not dp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dietary profile for {user_id} not found",
        )

    return DietaryProfileResponse(
        goal=dp.goal,
        activity=dp.activity,
        kcal_target=dp.kcal_target,
        protein_target_g=(
            float(dp.protein_target_g) if dp.protein_target_g is not None else None
        ),
        carb_target_g=float(dp.carb_target_g) if dp.carb_target_g is not None else None,
        fat_target_g=float(dp.fat_target_g) if dp.fat_target_g is not None else None,
        cuisine_likes=json.loads(dp.cuisine_likes) if dp.cuisine_likes else [],
        cuisine_dislikes=json.loads(dp.cuisine_dislikes) if dp.cuisine_dislikes else [],
        updated_at=dp.updated_at,
    )


@router.put("/users/{user_id}/dietary", response_model=DietaryProfileResponse)
def set_dietary_profile(
    user_id: UUID, profile: DietaryProfileCreate, db: Session = Depends(get_db)
):
    try:
        dp = ProfileService.set_dietary_profile(db, user_id, profile)
        return DietaryProfileResponse(
            goal=dp.goal,
            activity=dp.activity,
            kcal_target=dp.kcal_target,
            protein_target_g=(
                float(dp.protein_target_g) if dp.protein_target_g is not None else None
            ),
            carb_target_g=(
                float(dp.carb_target_g) if dp.carb_target_g is not None else None
            ),
            fat_target_g=(
                float(dp.fat_target_g) if dp.fat_target_g is not None else None
            ),
            cuisine_likes=json.loads(dp.cuisine_likes) if dp.cuisine_likes else [],
            cuisine_dislikes=(
                json.loads(dp.cuisine_dislikes) if dp.cuisine_dislikes else []
            ),
            updated_at=dp.updated_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/users/{user_id}/preferences", response_model=List[PreferenceResponse])
def get_preferences(user_id: UUID, db: Session = Depends(get_db)):
    prefs = ProfileService.get_preferences(db, user_id)
    return [PreferenceResponse.model_validate(p) for p in prefs]


@router.put("/users/{user_id}/preferences", response_model=List[PreferenceResponse])
def set_preferences(
    user_id: UUID, preferences: List[PreferenceCreate], db: Session = Depends(get_db)
):
    try:
        prefs = ProfileService.set_preferences(db, user_id, preferences)
        return [PreferenceResponse.model_validate(p) for p in prefs]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/users/{user_id}/allergies", response_model=List[AllergyResponse])
def get_allergies(user_id: UUID, db: Session = Depends(get_db)):
    allergies = ProfileService.get_allergies(db, user_id)
    return [AllergyResponse.model_validate(a) for a in allergies]


@router.put("/users/{user_id}/allergies", response_model=List[AllergyResponse])
def set_allergies(
    user_id: UUID, allergies: List[AllergyCreate], db: Session = Depends(get_db)
):
    try:
        al = ProfileService.set_allergies(db, user_id, allergies)
        return [AllergyResponse.model_validate(a) for a in al]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/users/{user_id}/preferences",
    response_model=PreferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_preference(
    user_id: UUID, preference: PreferenceCreate, db: Session = Depends(get_db)
):
    try:
        p = ProfileService.add_preference(db, user_id, preference)
        return PreferenceResponse.model_validate(p)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/users/{user_id}/preferences/{tag}")
def delete_preference(user_id: UUID, tag: str, db: Session = Depends(get_db)):
    success = ProfileService.remove_preference(db, user_id, tag)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preference {tag} not found for user {user_id}",
        )
    return {"status": "ok", "removed": tag}


@router.post(
    "/users/{user_id}/allergies",
    response_model=AllergyResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_allergy(user_id: UUID, allergy: AllergyCreate, db: Session = Depends(get_db)):
    try:
        a = ProfileService.add_allergy(db, user_id, allergy)
        return AllergyResponse.model_validate(a)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/users/{user_id}/allergies/{ingredient_id}")
def delete_allergy(user_id: UUID, ingredient_id: UUID, db: Session = Depends(get_db)):
    success = ProfileService.remove_allergy(db, user_id, ingredient_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Allergy {ingredient_id} not found for user {user_id}",
        )
    return {"status": "ok", "removed": str(ingredient_id)}


@router.get("/recommendations/{user_id}", response_model=List[RecipeRecommendation])
def get_recommendations(
        user_id: UUID,
        limit: int = 10,
        db: Session = Depends(get_db)
):
    """
    Get personalized recipe recommendations for a user.

    Usage:
      GET /recommendations/{user_id}           (returns 10 by default)
      GET /recommendations/{user_id}?limit=5   (returns 5)
    """
    try:
        recipes = RecommendationService.recommend(
            db=db,
            user_id=user_id,
            limit=limit,
            tag_filters=None
        )

        return [
            RecipeRecommendation.from_recipe(
                recipe,
                score=recipe.get("match_score", 0),
                pantry_matches=recipe.get("pantry_match_count", 0)
            )
            for recipe in recipes
        ]
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating recommendations"
        )
