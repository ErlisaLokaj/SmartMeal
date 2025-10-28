from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database.models import get_db
from core.schemas.profile_schemas import *
from core.services.profile_service import *

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("/{user_id}", response_model=UserProfileResponse)
def get_profile(
    user_id: UUID,
    db: Session = Depends(get_db)
):
    """
    Get complete user profile including dietary settings, allergies, and preferences.
    """
    user = ProfileService.get_user_profile(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )
    
    # Transform dietary profile
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
            cuisine_dislikes=json.loads(dp.cuisine_dislikes) if dp.cuisine_dislikes else [],
            updated_at=dp.updated_at
        )
    
    return UserProfileResponse(
        user_id=user.user_id,
        email=user.email,
        full_name=user.full_name,
        created_at=user.created_at,
        updated_at=user.updated_at,
        dietary_profile=dietary_response,
        allergies=[AllergyResponse.from_orm(a) for a in user.allergies],
        preferences=[PreferenceResponse.from_orm(p) for p in user.preferences]
    )


@router.put("/{user_id}", response_model=UserProfileResponse)
def update_profile(
    user_id: UUID,
    profile_data: ProfileUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update user profile, dietary settings, allergies, and preferences.
    This endpoint implements the complete sequence diagram flow.
    """
    try:
        user = ProfileService.upsert_profile(db, user_id, profile_data)
        
        # Transform response (same as GET)
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
                cuisine_dislikes=json.loads(dp.cuisine_dislikes) if dp.cuisine_dislikes else [],
                updated_at=dp.updated_at
            )
        
        return UserProfileResponse(
            user_id=user.user_id,
            email=user.email,
            full_name=user.full_name,
            created_at=user.created_at,
            updated_at=user.updated_at,
            dietary_profile=dietary_response,
            allergies=[AllergyResponse.from_orm(a) for a in user.allergies],
            preferences=[PreferenceResponse.from_orm(p) for p in user.preferences]
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error updating profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/users", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    email: EmailStr,
    full_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Create a new user"""
    try:
        user = ProfileService.create_user(db, email, full_name)
        
        return UserProfileResponse(
            user_id=user.user_id,
            email=user.email,
            full_name=user.full_name,
            created_at=user.created_at,
            updated_at=user.updated_at,
            dietary_profile=None,
            allergies=[],
            preferences=[]
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )