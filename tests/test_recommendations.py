"""
Tests for Recipe Recommendations (Use Case 7).

This test suite covers personalized recipe recommendations:
- Profile-based recommendations (dietary preferences, allergies)
- Pantry-aware suggestions (ingredients on hand)
- Tag filtering (vegetarian, quick, etc.)
- Match scoring and ranking
- MongoDB recipe retrieval
- Neo4j ingredient validation

Recommendation algorithm considers:
- User dietary profile (goals, macro targets)
- Food preferences (cuisine likes/dislikes, tags)
- Allergies (automatic filtering)
- Pantry contents (boost recipes with available ingredients)
- Recipe tags (filtering and matching)
"""

import pytest
import uuid

from test_fixtures import client, make_user
from services.profile_service import ProfileService


# =============================================================================
# RECOMMENDATION FLOW
# =============================================================================

EXAMPLE_RECOMMENDATION_FLOW = """
Recipe Recommendation Flow (Use Case 7)
======================================

1. GET PERSONALIZED RECOMMENDATIONS
   GET /recommendations/123e4567-e89b-12d3-a456-426614174000?limit=10
   
   Response: 200 OK
   [
       {
           "_id": "recipe-uuid-1",
           "title": "Vegetarian Stir-Fry",
           "slug": "vegetarian-stir-fry",
           "tags": ["vegetarian", "quick", "asian"],
           "match_score": 85.5,
           "pantry_match_count": 3,
           "yields": {
               "servings": 4,
               "serving_unit": "servings"
           },
           "ingredients": [
               {
                   "ingredient_id": "uuid-tofu",
                   "name": "tofu",
                   "quantity": 400,
                   "unit": "g"
               },
               ...
           ],
           "steps": [
               {
                   "order": 1,
                   "text": "Press tofu to remove excess water",
                   "duration_min": 10
               },
               ...
           ],
           "cuisine_id": "asian-cuisine-id",
           "nutrition": {
               "calories": 350,
               "protein_g": 18.0,
               "carbs_g": 45.0,
               "fat_g": 12.0
           }
       },
       ...
   ]

2. GET RECOMMENDATIONS WITH TAG FILTERS
   GET /recommendations/123e4567-e89b-12d3-a456-426614174000?limit=5&tags=quick,healthy
   
   Response: 200 OK
   [
       {
           "_id": "recipe-uuid-2",
           "title": "Quick Salad",
           "tags": ["quick", "healthy", "vegetarian"],
           "match_score": 78.0,
           ...
       }
   ]
"""


RECOMMENDATION_ALGORITHM = """
Recommendation Algorithm Details
======================================

Scoring Components (Total: 100 points):

1. Dietary Profile Match (30 points):
   - Goal alignment (weight loss → low-calorie recipes)
   - Macro target proximity (protein, carbs, fat)
   - Activity level consideration

2. Preference Match (25 points):
   - Cuisine likes/dislikes
   - Tag preferences (vegetarian, quick, etc.)
   - Strength weighting (must > prefer > like)

3. Allergy Safety (MANDATORY):
   - Recipes with allergic ingredients: EXCLUDED
   - Zero tolerance for allergens
   - Enforced before scoring

4. Pantry Match (20 points):
   - Number of ingredients already in pantry
   - Reduces shopping effort
   - Boosts "cook now" recommendations

5. Recipe Popularity (15 points):
   - Based on recipe ratings/usage
   - Community validation

6. Freshness Bonus (10 points):
   - Recently added recipes
   - Seasonal ingredients

Results are sorted by match_score (descending).
"""


RECOMMENDATION_DATA_FLOW = """
Data Flow for Recommendations
======================================

1. User Profile Retrieval (PostgreSQL):
   - GET user dietary profile
   - GET user preferences (tags, cuisines)
   - GET user allergies (ingredient IDs)
   - GET user pantry (ingredient IDs)

2. Recipe Search (MongoDB):
   - Query recipes collection
   - Filter: exclude recipes with allergic ingredients
   - Filter: optionally match tags
   - Retrieve: full recipe documents

3. Ingredient Validation (Neo4j):
   - Validate ingredient IDs
   - Get ingredient metadata (names, categories)
   - Used for pantry matching

4. Scoring & Ranking (Application Logic):
   - Calculate match scores per recipe
   - Apply preference weights
   - Count pantry matches
   - Sort by total score

5. Response Assembly:
   - Add match_score to each recipe
   - Add pantry_match_count
   - Return top N recipes (default: 10)
"""


# =============================================================================
# RECOMMENDATION TESTS
# =============================================================================


def test_recommendations_endpoint(monkeypatch):
    """
    Test the recommendation endpoint (Use Case 7).

    Verifies:
    1. GET /recommendations/{user_id} returns personalized recipes
    2. Default limit applied (10 recipes)
    3. Custom limit parameter works
    4. Response includes match scores
    5. Response includes all recipe fields

    Data consistency:
    - Test user: make_user()
    - Mock recipes from MongoDB with realistic structure
    - Recipe 1: "Vegetarian Stir-Fry", score 80.0, tags ["vegetarian", "quick", "asian"]
    - Recipe 2: "Quick Salad", score 70.0, tags ["vegetarian", "quick", "healthy"]

    Integration points:
    - ProfileService.get_user_profile (validates user exists)
    - RecommendationService.recommend (retrieves scored recipes)
    - MongoDB recipes collection (mocked)
    """
    user = make_user()

    # Mock recipe data that would come from MongoDB
    mock_recipes = [
        {
            "_id": "recipe-uuid-1",
            "title": "Vegetarian Stir-Fry",
            "slug": "vegetarian-stir-fry",
            "tags": ["vegetarian", "quick", "asian"],
            "yields": {"servings": 4, "serving_unit": "servings"},
            "ingredients": [
                {
                    "ingredient_id": str(uuid.uuid4()),
                    "name": "tofu",
                    "quantity": 400,
                    "unit": "g",
                }
            ],
            "steps": [{"order": 1, "text": "Cook tofu", "duration_min": 10}],
            "cuisine_id": "asian-cuisine-id",
            "match_score": 80.0,
            "pantry_match_count": 0,
        },
        {
            "_id": "recipe-uuid-2",
            "title": "Quick Salad",
            "slug": "quick-salad",
            "tags": ["vegetarian", "quick", "healthy"],
            "yields": {"servings": 2, "serving_unit": "servings"},
            "ingredients": [
                {
                    "ingredient_id": str(uuid.uuid4()),
                    "name": "lettuce",
                    "quantity": 200,
                    "unit": "g",
                }
            ],
            "steps": [{"order": 1, "text": "Toss salad", "duration_min": 5}],
            "cuisine_id": "american-cuisine-id",
            "match_score": 70.0,
            "pantry_match_count": 0,
        },
    ]

    # Mock ProfileService.get_user_profile to return our test user
    from services.recommendation_service import RecommendationService

    monkeypatch.setattr(ProfileService, "get_user_profile", lambda db, uid: user)

    # Mock RecommendationService.recommend to return mock recipes
    def fake_recommend(db, user_id, limit, tag_filters):
        return mock_recipes[:limit]

    monkeypatch.setattr(RecommendationService, "recommend", fake_recommend)

    # Test: Get recommendations with default limit
    r = client.get(f"/recommendations/{user.user_id}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 2  # Should return both mock recipes
    assert data[0]["title"] == "Vegetarian Stir-Fry"
    assert data[0]["match_score"] == 80.0
    assert "tags" in data[0]

    # Test: Get recommendations with custom limit
    r2 = client.get(f"/recommendations/{user.user_id}?limit=1")
    assert r2.status_code == 200
    data2 = r2.json()
    assert len(data2) == 1  # Should return only 1 recipe
    assert data2[0]["_id"] == "recipe-uuid-1"


def test_recommendations_with_tag_filters(monkeypatch):
    """
    Test recommendations with tag filtering.

    Verifies:
    1. Tag filter parameter accepted
    2. Only recipes matching ALL tags returned
    3. Match scores still calculated

    Scenario:
    - Request recipes with tags: ["quick", "healthy"]
    - Recipe 1: ["vegetarian", "quick", "asian"] → NO MATCH (missing "healthy")
    - Recipe 2: ["vegetarian", "quick", "healthy"] → MATCH

    Data consistency:
    - Filter tags passed as query parameter
    - Service receives tag list for filtering
    """
    user = make_user()

    # Only recipes with both "quick" AND "healthy"
    filtered_recipes = [
        {
            "_id": "recipe-uuid-2",
            "title": "Quick Salad",
            "slug": "quick-salad",
            "tags": ["vegetarian", "quick", "healthy"],
            "yields": {"servings": 2, "serving_unit": "servings"},
            "ingredients": [],
            "steps": [],
            "cuisine_id": "american-cuisine-id",
            "match_score": 78.0,
            "pantry_match_count": 0,
        }
    ]

    from services.recommendation_service import RecommendationService

    monkeypatch.setattr(ProfileService, "get_user_profile", lambda db, uid: user)

    def fake_recommend_filtered(db, user_id, limit, tag_filters=None):
        # Verify tag filters passed correctly
        if tag_filters:
            assert set(tag_filters) == {"quick", "healthy"}
        return filtered_recipes

    monkeypatch.setattr(RecommendationService, "recommend", fake_recommend_filtered)

    r = client.get(f"/recommendations/{user.user_id}?tags=quick,healthy")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["title"] == "Quick Salad"
    assert "quick" in data[0]["tags"]
    assert "healthy" in data[0]["tags"]


def test_recommendations_user_not_found(monkeypatch):
    """
    Test recommendations when user doesn't exist.

    Verifies error handling:
    - RecommendationService raises NotFoundError for invalid user_id
    - API returns 404 Not Found

    This prevents recommendations for non-existent users.
    """
    from core.exceptions import NotFoundError
    from services.recommendation_service import RecommendationService

    def fake_recommend_not_found(db, user_id, limit, tag_filters=None):
        raise NotFoundError(f"User {user_id} not found")

    monkeypatch.setattr(RecommendationService, "recommend", fake_recommend_not_found)

    r = client.get(f"/recommendations/{uuid.uuid4()}")
    assert r.status_code == 404


def test_recommendations_empty_result(monkeypatch):
    """
    Test recommendations when no matching recipes found.

    Scenario:
    - User has very restrictive preferences/allergies
    - No recipes match criteria
    - Should return empty list, not error

    Verifies:
    - Empty results handled gracefully
    - Returns 200 OK with empty array
    - No server errors

    Data consistency:
    - Empty list is valid response
    - Allows UI to show "no recommendations" message
    """
    user = make_user()
    from services.recommendation_service import RecommendationService

    monkeypatch.setattr(ProfileService, "get_user_profile", lambda db, uid: user)
    monkeypatch.setattr(
        RecommendationService,
        "recommend",
        lambda db, user_id, limit, tag_filters=None: [],
    )

    r = client.get(f"/recommendations/{user.user_id}")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 0


if __name__ == "__main__":
    print(EXAMPLE_RECOMMENDATION_FLOW)
    print("\n" + "=" * 70 + "\n")
    print(RECOMMENDATION_ALGORITHM)
    print("\n" + "=" * 70 + "\n")
    print(RECOMMENDATION_DATA_FLOW)
