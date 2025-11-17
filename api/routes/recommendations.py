"""
Recommendation routes - Personalized recipe recommendations.
Implements use case 7 (smart recommendations based on user profile and pantry).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import logging

from domain.models import get_db_session
from domain.schemas.recipe_schemas import RecipeRecommendation
from services.recommendation_service import RecommendationService
from app.exceptions import NotFoundError

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])
logger = logging.getLogger("smartmeal.api.recommendations")

from sqlalchemy import text

@router.post("/users/{user_id}/preferences")
def add_user_preferences(
    user_id: UUID,
    preferences: List[dict],
    db: Session = Depends(get_db_session)
):
    """
    Add or update user tag-based preferences for a given user.
    """
    try:
        for pref in preferences:
            db.execute(
                text("""
                    INSERT INTO user_preference (user_id, tag, strength)
                    VALUES (:uid, :tag, :strength)
                    ON CONFLICT (user_id, tag) DO UPDATE SET strength = EXCLUDED.strength
                """),
                {"uid": str(user_id), "tag": pref["tag"], "strength": pref["strength"]}
            )
        db.commit()
        return {
            "success": True,
            "message": f"Saved {len(preferences)} preferences for user {user_id}"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add preferences: {str(e)}")


@router.get("/{user_id}", response_model=List[RecipeRecommendation])
def get_recommendations(
    user_id: UUID, limit: int = 10, db: Session = Depends(get_db_session)
) -> List[RecipeRecommendation]:
    """
    Get personalized recipe recommendations for a user.

    Algorithm considers:
    - User's dietary profile (cuisine preferences, goals)
    - Pantry inventory (prioritizes recipes using available ingredients)
    - Allergens (excludes recipes with allergic ingredients)
    - Tag preferences (vegetarian, quick, healthy, etc.)
    - Diversity (avoids repeating recently cooked recipes)

    Args:
        user_id: User UUID
        limit: Maximum number of recommendations (default 10)

    Returns:
        List of recommended recipes with match scores
    """
    recommendations = RecommendationService.recommend(
        db=db,
        user_id=user_id,
        limit=limit,
        tag_filters=None,  # Use user's preference tags
    )

    # Convert to response schema
    return [
        RecipeRecommendation.from_recipe(
            recipe=rec,
            score=rec.get("match_score", 0),
            pantry_matches=rec.get("pantry_match_count", 0),
        )
        for rec in recommendations
    ]
