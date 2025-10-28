"""Recommendation service for Smart Meal: On-demand Recommendations."""

import logging
from typing import List, Set
from uuid import UUID
from sqlalchemy.orm import Session

from core.database.models import AppUser, PantryItem
from adapters import mongo_adapter

logger = logging.getLogger("smartmeal.recommendations")


class RecommendationService:
    """Business logic for recipe recommendations."""

    @staticmethod
    def recommend(
            db: Session,
            user_id: UUID,
            limit: int = 10,
            tag_filters: List[str] = None
    ) -> List[dict]:
        """Generate personalized recipe recommendations.

        Algorithm:
        1. Get user profile (dietary preferences, allergies, cuisine likes/dislikes)
        2. Get user's pantry items
        3. Search candidate recipes from MongoDB
        4. Filter out recipes with allergens
        5. Score recipes based on:
           - Cuisine match
           - Tag preferences
           - Pantry ingredient usage
           - Dietary goals
        6. Return top K ranked recipes

        Args:
            db: Database session
            user_id: User UUID
            limit: Maximum number of recommendations
            tag_filters: Optional list of tags to filter by

        Returns:
            List of recipe documents with match scores
        """
        logger.info(f"Generating recommendations for user {user_id}")

        # 1. Get user profile
        user = db.query(AppUser).filter(AppUser.user_id == user_id).first()
        if not user:
            logger.warning(f"User {user_id} not found")
            return []

        # 2. Extract user preferences
        cuisine_likes = []
        cuisine_dislikes = []
        if user.dietary_profile:
            import json
            cuisine_likes = json.loads(user.dietary_profile.cuisine_likes or "[]")
            cuisine_dislikes = json.loads(user.dietary_profile.cuisine_dislikes or "[]")

        # Get user preference tags
        preference_tags = [p.tag for p in user.preferences if p.strength in ["like", "love"]]
        avoid_tags = [p.tag for p in user.preferences if p.strength == "avoid"]

        # Get allergen ingredient IDs
        allergen_ids = [str(a.ingredient_id) for a in user.allergies]

        # 3. Get pantry items (for bonus scoring)
        pantry_items = db.query(PantryItem).filter(PantryItem.user_id == user_id).all()
        pantry_ingredient_ids = {str(item.ingredient_id) for item in pantry_items}

        logger.info(
            f"User preferences: cuisine_likes={cuisine_likes}, "
            f"preference_tags={preference_tags}, allergens={len(allergen_ids)}, "
            f"pantry_items={len(pantry_ingredient_ids)}"
        )

        # 4. Build tag filters
        search_tags = tag_filters if tag_filters else preference_tags

        # 5. Search candidate recipes from MongoDB
        candidate_recipes = mongo_adapter.search_recipes(
            tags=search_tags if search_tags else None,
            exclude_ingredient_ids=allergen_ids,
            limit=limit * 3  # Get more candidates for better ranking
        )

        # If no results with tags, get random recipes (excluding allergens)
        if not candidate_recipes:
            logger.info("No recipes found with preference tags, getting random recipes")
            candidate_recipes = mongo_adapter.search_recipes(
                exclude_ingredient_ids=allergen_ids,
                limit=limit * 2
            )

        logger.info(f"Found {len(candidate_recipes)} candidate recipes")

        # 6. Score and rank recipes
        scored_recipes = []
        for recipe in candidate_recipes:
            score = RecommendationService._score_recipe(
                recipe=recipe,
                cuisine_likes=cuisine_likes,
                cuisine_dislikes=cuisine_dislikes,
                preference_tags=preference_tags,
                avoid_tags=avoid_tags,
                pantry_ingredient_ids=pantry_ingredient_ids
            )

            # Calculate pantry matches
            recipe_ingredient_ids = {
                ing.get("ingredient_id")
                for ing in recipe.get("ingredients", [])
            }
            pantry_matches = len(recipe_ingredient_ids & pantry_ingredient_ids)

            recipe["match_score"] = score
            recipe["pantry_match_count"] = pantry_matches
            scored_recipes.append(recipe)

        # 7. Sort by score (descending) and return top K
        scored_recipes.sort(key=lambda r: r["match_score"], reverse=True)
        top_recipes = scored_recipes[:limit]

        logger.info(
            f"Returning {len(top_recipes)} recommendations "
            f"(scores: {[r['match_score'] for r in top_recipes[:3]]})"
        )

        return top_recipes

    @staticmethod
    def _score_recipe(
            recipe: dict,
            cuisine_likes: List[str],
            cuisine_dislikes: List[str],
            preference_tags: List[str],
            avoid_tags: List[str],
            pantry_ingredient_ids: Set[str]
    ) -> float:
        """Score a recipe based on user preferences.

        Scoring breakdown:
        - Base score: 50
        - Cuisine match: +30 for liked, -50 for disliked
        - Tag match: +10 per matching preference tag
        - Avoid tag: -20 per avoid tag
        - Pantry usage: +5 per pantry ingredient used
        - Diversity bonus: +10 for recipes with unique tags

        Returns:
            Score (0-100 range typical)
        """
        score = 50.0  # Base score

        # Cuisine scoring
        recipe_cuisine = recipe.get("cuisine_id", "").lower()
        if any(like.lower() in recipe_cuisine for like in cuisine_likes):
            score += 30
        if any(dislike.lower() in recipe_cuisine for dislike in cuisine_dislikes):
            score -= 50

        # Tag preference scoring
        recipe_tags = [tag.lower() for tag in recipe.get("tags", [])]

        for pref_tag in preference_tags:
            if pref_tag.lower() in recipe_tags:
                score += 10

        for avoid_tag in avoid_tags:
            if avoid_tag.lower() in recipe_tags:
                score -= 20

        # Pantry usage bonus
        recipe_ingredient_ids = {
            ing.get("ingredient_id")
            for ing in recipe.get("ingredients", [])
        }
        pantry_matches = len(recipe_ingredient_ids & pantry_ingredient_ids)
        score += pantry_matches * 5

        # Diversity bonus (recipes with uncommon tags)
        if len(recipe_tags) > 3:
            score += 10

        return max(0, score)  # Don't return negative scores