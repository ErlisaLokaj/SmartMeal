"""
User domain mappers.
Handles transformation between ORM models and DTOs for user-related entities.
"""

import json
from typing import Optional
from domain.models import AppUser
from domain.schemas.profile_schemas import (
    UserProfileResponse,
    DietaryProfileResponse,
    AllergyResponse,
    PreferenceResponse,
)


class UserMapper:
    """Mapper for user-related transformations."""

    @staticmethod
    def to_response(user: AppUser) -> UserProfileResponse:
        """
        Convert AppUser ORM model to UserProfileResponse DTO.

        Args:
            user: AppUser ORM instance with relationships loaded

        Returns:
            UserProfileResponse DTO with all user data
        """
        dietary_response: Optional[DietaryProfileResponse] = None
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
            preferences=[
                PreferenceResponse.model_validate(p) for p in user.preferences
            ],
        )
