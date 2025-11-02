"""
Tests for User Management and Profile Operations (Use Cases 1 & 2).

This test suite covers:
- Use Case 1: Create and Manage User Profile
  - User registration (email, full name)
  - Profile retrieval
  - Profile updates (PUT with upsert semantics)
  - User deletion

- Use Case 2: Set Dietary Preferences & Allergies
  - Dietary profile management (goals, activity, macro targets)
  - Food preferences (tags, strengths)
  - Allergy management (ingredient-based)
"""

import pytest
import uuid
from types import SimpleNamespace
from datetime import datetime

from test_fixtures import client, make_user
from services.profile_service import ProfileService
from core.exceptions import ServiceValidationError


# =============================================================================
# USER PROFILE MANAGEMENT FLOW
# =============================================================================

EXAMPLE_USER_FLOW = """
User Profile Management Flow (Use Case 1)
======================================

1. CREATE NEW USER
   POST /users
   {
       "email": "john.doe@example.com",
       "full_name": "John Doe"
   }
   
   Response: 201 Created
   {
       "user_id": "123e4567-e89b-12d3-a456-426614174000",
       "email": "john.doe@example.com",
       "full_name": "John Doe",
       "created_at": "2025-11-01T10:00:00Z",
       "updated_at": "2025-11-01T10:00:00Z"
   }

2. GET USER PROFILE
   GET /users/123e4567-e89b-12d3-a456-426614174000
   
   Response: 200 OK
   {
       "user_id": "123e4567-e89b-12d3-a456-426614174000",
       "email": "john.doe@example.com",
       "full_name": "John Doe",
       ...
   }

3. UPDATE PROFILE (UPSERT)
   PUT /profiles/123e4567-e89b-12d3-a456-426614174000
   {
       "full_name": "John M. Doe",
       "email": "john.m.doe@example.com"
   }
   
   Response: 200 OK (update) or 201 Created (new profile)
   Location: /profiles/123e4567-e89b-12d3-a456-426614174000

4. DELETE USER
   DELETE /users/123e4567-e89b-12d3-a456-426614174000
   
   Response: 200 OK
   {
       "status": "ok",
       "deleted": "123e4567-e89b-12d3-a456-426614174000"
   }
"""


EXAMPLE_DIETARY_FLOW = """
Dietary Preferences & Allergies Flow (Use Case 2)
======================================

1. SET DIETARY PROFILE
   PUT /profiles/123e4567-e89b-12d3-a456-426614174000/dietary
   {
       "goal": "weight_loss",
       "activity": "moderate",
       "kcal_target": 1800,
       "protein_target_g": 120.0,
       "carb_target_g": 180.0,
       "fat_target_g": 60.0,
       "cuisine_likes": ["italian", "asian"],
       "cuisine_dislikes": ["spicy"]
   }
   
   Response: 200 OK

2. SET FOOD PREFERENCES
   PUT /profiles/123e4567-e89b-12d3-a456-426614174000/preferences
   [
       {"tag": "vegetarian", "strength": "must"},
       {"tag": "low-carb", "strength": "like"},
       {"tag": "quick", "strength": "prefer"}
   ]
   
   Response: 200 OK

3. ADD SINGLE PREFERENCE
   POST /profiles/123e4567-e89b-12d3-a456-426614174000/preferences
   {
       "tag": "vegan",
       "strength": "like"
   }
   
   Response: 201 Created

4. SET ALLERGIES
   PUT /profiles/123e4567-e89b-12d3-a456-426614174000/allergies
   [
       {
           "ingredient_id": "uuid-peanuts",
           "note": "Severe allergy - avoid all nuts"
       },
       {
           "ingredient_id": "uuid-shellfish",
           "note": "Moderate reaction"
       }
   ]
   
   Response: 200 OK

5. REMOVE PREFERENCE
   DELETE /profiles/123e4567-e89b-12d3-a456-426614174000/preferences/vegan
   
   Response: 200 OK
"""


# =============================================================================
# USER TESTS
# =============================================================================


def test_users_list_and_create_and_get_and_delete(monkeypatch):
    """
    Integration test for user CRUD operations.

    This test verifies:
    1. GET /users - List all users
    2. POST /users - Create new user
    3. GET /users/{user_id} - Get specific user
    4. DELETE /users/{user_id} - Delete user

    Data consistency:
    - Uses make_user() to create consistent mock user objects
    - User email: test@example.com
    - User name: Test User
    """
    user = make_user()

    # Test: List all users
    monkeypatch.setattr(ProfileService, "get_all_users", lambda db: [user])
    r = client.get("/users")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # Test: Create new user
    created = make_user()

    def fake_create(db, email, full_name=None):
        return created

    monkeypatch.setattr(ProfileService, "create_user", fake_create)
    r2 = client.post("/users", json={"email": "a@b.com", "full_name": "A B"})
    assert r2.status_code == 201
    assert r2.json()["email"] == created.email

    # Test: Get user profile
    monkeypatch.setattr(ProfileService, "get_user_profile", lambda db, uid: user)
    r3 = client.get(f"/users/{user.user_id}")
    assert r3.status_code == 200
    assert r3.json()["user_id"] == str(user.user_id)

    # Test: Delete user
    monkeypatch.setattr(ProfileService, "delete_user", lambda db, uid: True)
    r4 = client.delete(f"/users/{user.user_id}")
    assert r4.status_code == 200
    assert r4.json()["deleted"] == str(user.user_id)


def test_update_profile(monkeypatch):
    """
    Test profile update (existing profile).

    Verifies PUT /profiles/{user_id} updates existing profile.
    Service returns (user, False) indicating update, not creation.

    Expected: 200 OK response
    """
    user = make_user()

    def fake_upsert(db, uid, profile_data):
        # mimic new service signature returning (user, created_flag)
        return user, False

    monkeypatch.setattr(ProfileService, "upsert_profile", fake_upsert)
    payload = {"full_name": "Updated"}
    r = client.put(f"/profiles/{user.user_id}", json=payload)
    assert r.status_code == 200
    assert r.json()["full_name"] == user.full_name


def test_update_profile_create_on_put(monkeypatch):
    """
    Test profile creation via PUT (upsert semantics).

    When the service indicates a creation happened, route should:
    - Return 201 Created status
    - Include Location header pointing to new resource

    This follows RESTful conventions for PUT with resource creation.
    """
    created_user = make_user()

    def fake_upsert_created(db, uid, profile_data):
        return created_user, True

    monkeypatch.setattr(ProfileService, "upsert_profile", fake_upsert_created)
    payload = {"full_name": "New User", "email": "new@example.com"}
    r = client.put(f"/profiles/{created_user.user_id}", json=payload)
    assert r.status_code == 201
    # Location header should be set to new resource
    assert r.headers.get("location") == f"/profiles/{created_user.user_id}"
    body = r.json()
    assert body["user_id"] == str(created_user.user_id)


def test_update_profile_service_error(monkeypatch):
    """
    Test error handling for profile update failures.

    Service validation errors should return 400 Bad Request.
    This ensures proper error propagation from service layer.
    """
    user = make_user()

    def fake_upsert_error(db, uid, profile_data):
        raise ServiceValidationError("User not found")

    monkeypatch.setattr(ProfileService, "upsert_profile", fake_upsert_error)
    r = client.put(f"/profiles/{user.user_id}", json={"full_name": "X"})
    assert r.status_code == 400


# =============================================================================
# DIETARY PROFILE TESTS
# =============================================================================


def test_dietary_get_set(monkeypatch):
    """
    Test dietary profile management.

    Verifies:
    1. GET /profiles/{user_id}/dietary - Retrieve dietary settings
    2. PUT /profiles/{user_id}/dietary - Update dietary settings

    Dietary profile includes:
    - Nutrition goals (maintenance, weight_loss, muscle_gain)
    - Activity level (sedentary, light, moderate, active, very_active)
    - Macro targets (calories, protein, carbs, fat)
    - Cuisine preferences (likes/dislikes)

    Data consistency:
    - kcal_target: 2000
    - protein_target_g: 100.0
    - carb_target_g: 250.0
    - fat_target_g: 70.0
    """
    user = make_user()
    # Create a fake dietary profile object
    dp = SimpleNamespace(
        goal="maintenance",
        activity="moderate",
        kcal_target=2000,
        protein_target_g=100.0,
        carb_target_g=250.0,
        fat_target_g=70.0,
        cuisine_likes="[]",
        cuisine_dislikes="[]",
        updated_at=datetime.utcnow(),
    )

    # Test: Get dietary profile
    monkeypatch.setattr(ProfileService, "get_dietary_profile", lambda db, uid: dp)
    r = client.get(f"/profiles/{user.user_id}/dietary")
    assert r.status_code == 200
    assert r.json()["kcal_target"] == dp.kcal_target

    # Test: Set dietary profile
    monkeypatch.setattr(ProfileService, "set_dietary_profile", lambda db, uid, p: dp)
    payload = {"goal": "maintenance", "activity": "moderate", "kcal_target": 2000}
    r2 = client.put(f"/profiles/{user.user_id}/dietary", json=payload)
    assert r2.status_code == 200
    assert r2.json()["goal"] == dp.goal


# =============================================================================
# PREFERENCES TESTS
# =============================================================================


def test_preferences_bulk_and_single(monkeypatch):
    """
    Test food preference management (bulk and individual operations).

    Verifies:
    1. GET /profiles/{user_id}/preferences - List all preferences
    2. PUT /profiles/{user_id}/preferences - Replace all preferences (bulk)
    3. POST /profiles/{user_id}/preferences - Add single preference
    4. DELETE /profiles/{user_id}/preferences/{tag} - Remove preference

    Preference structure:
    - tag: Category/type of preference (e.g., "vegan", "low-carb")
    - strength: Preference intensity ("must", "prefer", "like", "avoid")

    Data consistency:
    - Test preference: {"tag": "vegan", "strength": "like"}
    """
    user = make_user()
    pref = SimpleNamespace(tag="vegan", strength="like")

    # Test: Get all preferences
    monkeypatch.setattr(ProfileService, "get_preferences", lambda db, uid: [pref])
    r = client.get(f"/profiles/{user.user_id}/preferences")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # Test: Set preferences (bulk replace)
    monkeypatch.setattr(
        ProfileService, "set_preferences", lambda db, uid, prefs: [pref]
    )
    r2 = client.put(
        f"/profiles/{user.user_id}/preferences",
        json=[{"tag": "vegan", "strength": "like"}],
    )
    assert r2.status_code == 200

    # Test: Add single preference
    monkeypatch.setattr(ProfileService, "add_preference", lambda db, uid, p: pref)
    r3 = client.post(
        f"/profiles/{user.user_id}/preferences",
        json={"tag": "vegan", "strength": "like"},
    )
    assert r3.status_code == 201

    # Test: Remove preference
    monkeypatch.setattr(ProfileService, "remove_preference", lambda db, uid, tag: True)
    r4 = client.delete(f"/profiles/{user.user_id}/preferences/vegan")
    assert r4.status_code == 200


# =============================================================================
# ALLERGY TESTS
# =============================================================================


def test_allergies_bulk_and_single(monkeypatch):
    """
    Test allergy management (bulk and individual operations).

    Verifies:
    1. GET /profiles/{user_id}/allergies - List all allergies
    2. PUT /profiles/{user_id}/allergies - Replace all allergies (bulk)
    3. POST /profiles/{user_id}/allergies - Add single allergy
    4. DELETE /profiles/{user_id}/allergies/{ingredient_id} - Remove allergy

    Allergy structure:
    - ingredient_id: UUID of allergic ingredient (from Neo4j)
    - note: Optional severity/description

    Integration with recipes:
    - Allergies are used to filter out recipes containing prohibited ingredients
    - Enforced in Use Case 3 (Search Recipes) and Use Case 7 (Recommendations)
    """
    user = make_user()
    allergy = SimpleNamespace(ingredient_id=uuid.uuid4(), note="nuts")

    # Test: Get all allergies
    monkeypatch.setattr(ProfileService, "get_allergies", lambda db, uid: [allergy])
    r = client.get(f"/profiles/{user.user_id}/allergies")
    assert r.status_code == 200

    # Test: Set allergies (bulk replace)
    monkeypatch.setattr(ProfileService, "set_allergies", lambda db, uid, a: [allergy])
    r2 = client.put(
        f"/profiles/{user.user_id}/allergies",
        json=[{"ingredient_id": str(allergy.ingredient_id), "note": "nuts"}],
    )
    assert r2.status_code == 200

    # Test: Add single allergy
    monkeypatch.setattr(ProfileService, "add_allergy", lambda db, uid, a: allergy)
    r3 = client.post(
        f"/profiles/{user.user_id}/allergies",
        json={"ingredient_id": str(allergy.ingredient_id), "note": "nuts"},
    )
    assert r3.status_code == 201

    # Test: Remove allergy
    monkeypatch.setattr(ProfileService, "remove_allergy", lambda db, uid, iid: True)
    r4 = client.delete(f"/profiles/{user.user_id}/allergies/{allergy.ingredient_id}")
    assert r4.status_code == 200


if __name__ == "__main__":
    print(EXAMPLE_USER_FLOW)
    print("\n" + "=" * 70 + "\n")
    print(EXAMPLE_DIETARY_FLOW)

