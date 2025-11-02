import uuid
from types import SimpleNamespace
from datetime import datetime
import importlib

# Prevent SQLAlchemy from importing DBAPI (psycopg2) during module import.
import sqlalchemy

_real_create_engine = getattr(sqlalchemy, "create_engine", None)


def _dummy_create_engine(*args, **kwargs):
    # simple dummy engine object; init_database is disabled below so it won't be used.
    return SimpleNamespace(begin=lambda *a, **k: None)


sqlalchemy.create_engine = _dummy_create_engine

# Import models and disable their init_database so TestClient startup is safe.
import domain.models as db_models

db_models.init_database = lambda: None

# Restore original create_engine in case other imports need it
if _real_create_engine is not None:
    sqlalchemy.create_engine = _real_create_engine

from fastapi.testclient import TestClient
import pytest

from main import app
from services.profile_service import ProfileService
from services.pantry_service import PantryService
from services.waste_service import WasteService
from domain.schemas.profile_schemas import PantryItemCreate
from domain.schemas.waste_schemas import WasteLogResponse, WasteInsightsResponse
from core.exceptions import ServiceValidationError, NotFoundError
from decimal import Decimal

# Create TestClient after we've disabled DB init
client = TestClient(app)


def make_user(user_id=None):
    uid = user_id or uuid.uuid4()
    now = datetime.utcnow()
    # SimpleNamespace to mimic ORM with attributes accessed in routes
    user = SimpleNamespace(
        user_id=uid,
        email="test@example.com",
        full_name="Test User",
        created_at=now,
        updated_at=now,
        dietary_profile=None,
        allergies=[],
        preferences=[],
    )
    return user


def make_pantry_item(pantry_item_id=None, user_id=None):
    return SimpleNamespace(
        pantry_item_id=pantry_item_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        ingredient_id=uuid.uuid4(),
        quantity=1.0,
        unit="pcs",
        best_before=None,
        source=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def test_health_check():
    r = client.get("/health-check")
    assert r.status_code == 200
    assert r.json()["service"] == "SmartMeal"


def test_users_list_and_create_and_get_and_delete(monkeypatch):
    user = make_user()

    monkeypatch.setattr(ProfileService, "get_all_users", lambda db: [user])
    r = client.get("/users")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # create_user
    created = make_user()

    def fake_create(db, email, full_name=None):
        return created

    monkeypatch.setattr(ProfileService, "create_user", fake_create)
    r2 = client.post("/users", json={"email": "a@b.com", "full_name": "A B"})
    assert r2.status_code == 201
    assert r2.json()["email"] == created.email

    # get_profile
    monkeypatch.setattr(ProfileService, "get_user_profile", lambda db, uid: user)
    r3 = client.get(f"/users/{user.user_id}")
    assert r3.status_code == 200
    assert r3.json()["user_id"] == str(user.user_id)

    # delete
    monkeypatch.setattr(ProfileService, "delete_user", lambda db, uid: True)
    r4 = client.delete(f"/users/{user.user_id}")
    assert r4.status_code == 200
    assert r4.json()["deleted"] == str(user.user_id)


def test_update_profile(monkeypatch):
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
    # When the service indicates a creation happened, route should return 201 and Location header
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


def test_dietary_get_set(monkeypatch):
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
    monkeypatch.setattr(ProfileService, "get_dietary_profile", lambda db, uid: dp)
    r = client.get(f"/profiles/{user.user_id}/dietary")
    assert r.status_code == 200
    assert r.json()["kcal_target"] == dp.kcal_target

    monkeypatch.setattr(ProfileService, "set_dietary_profile", lambda db, uid, p: dp)
    payload = {"goal": "maintenance", "activity": "moderate", "kcal_target": 2000}
    r2 = client.put(f"/profiles/{user.user_id}/dietary", json=payload)
    assert r2.status_code == 200
    assert r2.json()["goal"] == dp.goal


def test_preferences_bulk_and_single(monkeypatch):
    user = make_user()
    pref = SimpleNamespace(tag="vegan", strength="like")
    monkeypatch.setattr(ProfileService, "get_preferences", lambda db, uid: [pref])
    r = client.get(f"/profiles/{user.user_id}/preferences")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    monkeypatch.setattr(
        ProfileService, "set_preferences", lambda db, uid, prefs: [pref]
    )
    r2 = client.put(
        f"/profiles/{user.user_id}/preferences",
        json=[{"tag": "vegan", "strength": "like"}],
    )
    assert r2.status_code == 200

    monkeypatch.setattr(ProfileService, "add_preference", lambda db, uid, p: pref)
    r3 = client.post(
        f"/profiles/{user.user_id}/preferences",
        json={"tag": "vegan", "strength": "like"},
    )
    assert r3.status_code == 201

    monkeypatch.setattr(ProfileService, "remove_preference", lambda db, uid, tag: True)
    r4 = client.delete(f"/profiles/{user.user_id}/preferences/vegan")
    assert r4.status_code == 200


def test_allergies_bulk_and_single(monkeypatch):
    user = make_user()
    allergy = SimpleNamespace(ingredient_id=uuid.uuid4(), note="nuts")
    monkeypatch.setattr(ProfileService, "get_allergies", lambda db, uid: [allergy])
    r = client.get(f"/profiles/{user.user_id}/allergies")
    assert r.status_code == 200

    monkeypatch.setattr(ProfileService, "set_allergies", lambda db, uid, a: [allergy])
    r2 = client.put(
        f"/profiles/{user.user_id}/allergies",
        json=[{"ingredient_id": str(allergy.ingredient_id), "note": "nuts"}],
    )
    assert r2.status_code == 200

    monkeypatch.setattr(ProfileService, "add_allergy", lambda db, uid, a: allergy)
    r3 = client.post(
        f"/profiles/{user.user_id}/allergies",
        json={"ingredient_id": str(allergy.ingredient_id), "note": "nuts"},
    )
    assert r3.status_code == 201

    monkeypatch.setattr(ProfileService, "remove_allergy", lambda db, uid, iid: True)
    r4 = client.delete(f"/profiles/{user.user_id}/allergies/{allergy.ingredient_id}")
    assert r4.status_code == 200


def test_pantry_endpoints(monkeypatch):
    user = make_user()
    item = make_pantry_item(user_id=user.user_id)

    # Mock validation to return fake metadata
    def fake_validate(ingredient_id):
        return {
            "name": "Test Ingredient",
            "category": "vegetable",
            "perishability": "perishable",
            "defaults": {"shelf_life_days": 7},
        }

    def fake_validate_batch(ingredient_ids):
        return {str(iid): fake_validate(iid) for iid in ingredient_ids}

    monkeypatch.setattr(
        PantryService, "validate_ingredient_data", lambda iid: fake_validate(iid)
    )
    monkeypatch.setattr(
        PantryService,
        "validate_ingredients_batch",
        lambda iids: fake_validate_batch(iids),
    )
    monkeypatch.setattr(PantryService, "get_pantry", lambda db, uid: [item])
    r = client.get(f"/pantry?user_id={user.user_id}")
    assert r.status_code == 200

    monkeypatch.setattr(PantryService, "set_pantry", lambda db, uid, items: [item])
    r2 = client.put(
        "/pantry",
        json={
            "user_id": str(user.user_id),
            "items": [
                {
                    "ingredient_id": str(item.ingredient_id),
                    "quantity": 1.0,
                    "unit": "pcs",
                }
            ],
        },
    )
    assert r2.status_code == 200

    monkeypatch.setattr(PantryService, "add_item", lambda db, uid, it: item)
    r3 = client.post(
        "/pantry",
        json={
            "user_id": str(user.user_id),
            "item": {
                "ingredient_id": str(item.ingredient_id),
                "quantity": 1.0,
                "unit": "pcs",
            },
        },
    )
    assert r3.status_code == 201

    monkeypatch.setattr(PantryService, "remove_item", lambda db, pid: True)
    r4 = client.delete(f"/pantry/{item.pantry_item_id}")
    assert r4.status_code == 200


def test_update_profile_service_error(monkeypatch):
    user = make_user()

    def fake_upsert_error(db, uid, profile_data):
        raise ServiceValidationError("User not found")

    monkeypatch.setattr(ProfileService, "upsert_profile", fake_upsert_error)
    r = client.put(f"/profiles/{user.user_id}", json={"full_name": "X"})
    assert r.status_code == 400


def test_pantry_quantity_validation_and_response(monkeypatch):
    # Validation: quantity must be > 0
    user = make_user()
    item = make_pantry_item(user_id=user.user_id)

    # Mock validation to return fake metadata
    def fake_validate(ingredient_id):
        return {
            "name": "Test Ingredient",
            "category": "vegetable",
            "perishability": "perishable",
            "defaults": {"shelf_life_days": 7},
        }

    monkeypatch.setattr(
        PantryService, "validate_ingredient_data", lambda iid: fake_validate(iid)
    )

    # invalid quantity -> 422 from FastAPI/Pydantic
    r = client.post(
        "/pantry",
        json={
            "user_id": str(user.user_id),
            "item": {
                "ingredient_id": str(item.ingredient_id),
                "quantity": 0,
                "unit": "pcs",
            },
        },
    )
    assert r.status_code == 422

    # valid quantity -> use monkeypatched service to return an item and assert body
    returned = make_pantry_item(user_id=user.user_id)
    returned.quantity = 3.5
    returned.best_before = datetime.utcnow().date()

    monkeypatch.setattr(PantryService, "add_item", lambda db, uid, it: returned)
    r2 = client.post(
        "/pantry",
        json={
            "user_id": str(user.user_id),
            "item": {
                "ingredient_id": str(item.ingredient_id),
                "quantity": 3.5,
                "unit": "pcs",
            },
        },
    )
    assert r2.status_code == 201
    body = r2.json()
    assert float(body["quantity"]) == 3.5


# ========== Waste Management Tests ==========


def make_waste_log(waste_id=None, user_id=None, ingredient_id=None):
    """Create a mock waste log object"""
    return SimpleNamespace(
        waste_id=waste_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        ingredient_id=ingredient_id or uuid.uuid4(),
        quantity=Decimal("2.5"),
        unit="kg",
        reason="expired",
        occurred_at=datetime.utcnow(),
    )


def test_log_waste_success(monkeypatch):
    """Test successful waste logging"""
    user_id = uuid.uuid4()
    waste_log = make_waste_log(user_id=user_id)

    # Mock WasteService.validate_waste_data
    def fake_validate(ingredient_id, quantity, unit):
        return {
            "ingredient_id": ingredient_id,
            "quantity": quantity,
            "unit": unit,
            "ingredient_name": "Test Ingredient",
            "category": "test",
        }

    # Mock WasteService.log_waste
    def fake_log_waste(db, uid, waste_data):
        return WasteLogResponse.model_validate(waste_log)

    monkeypatch.setattr(WasteService, "validate_waste_data", fake_validate)
    monkeypatch.setattr(WasteService, "log_waste", fake_log_waste)

    r = client.post(
        f"/waste?user_id={user_id}",
        json={
            "ingredient_id": str(waste_log.ingredient_id),
            "quantity": 2.5,
            "unit": "kg",
            "reason": "expired",
        },
    )

    assert r.status_code == 201
    body = r.json()
    assert body["user_id"] == str(user_id)
    assert float(body["quantity"]) == 2.5
    assert body["unit"] == "kg"
    assert body["reason"] == "expired"


def test_log_waste_user_not_found(monkeypatch):
    """Test waste logging when user not found"""
    user_id = uuid.uuid4()

    # Mock WasteService.validate_waste_data
    def fake_validate(ingredient_id, quantity, unit):
        return {
            "ingredient_id": ingredient_id,
            "quantity": quantity,
            "unit": unit,
            "ingredient_name": "Test Ingredient",
            "category": "test",
        }

    def fake_log_waste_error(db, uid, waste_data):
        raise NotFoundError(f"User {uid} not found")

    monkeypatch.setattr(WasteService, "validate_waste_data", fake_validate)
    monkeypatch.setattr(WasteService, "log_waste", fake_log_waste_error)

    r = client.post(
        f"/waste?user_id={user_id}",
        json={
            "ingredient_id": str(uuid.uuid4()),
            "quantity": 1.0,
            "unit": "kg",
        },
    )

    assert r.status_code == 404


def test_log_waste_validation_error(monkeypatch):
    """Test waste logging with validation error"""
    user_id = uuid.uuid4()

    def fake_log_waste_validation_error(db, uid, waste_data):
        raise ServiceValidationError("Quantity must be greater than 0")

    monkeypatch.setattr(WasteService, "log_waste", fake_log_waste_validation_error)

    r = client.post(
        f"/waste?user_id={user_id}",
        json={
            "ingredient_id": str(uuid.uuid4()),
            "quantity": 0,
            "unit": "kg",
        },
    )

    # Should be 422 from Pydantic validation before it reaches the service
    assert r.status_code == 422


def test_get_waste_insights_success(monkeypatch):
    """Test successful retrieval of waste insights"""
    user_id = uuid.uuid4()

    # Create mock insights response
    from domain.schemas.waste_schemas import (
        WasteByIngredient,
        WasteByCategory,
        WasteTrend,
    )

    mock_insights = WasteInsightsResponse(
        total_waste_count=10,
        total_quantity=Decimal("25.5"),
        most_wasted_ingredients=[
            WasteByIngredient(
                ingredient_id=uuid.uuid4(),
                ingredient_name="Tomato",
                total_quantity=Decimal("10.0"),
                unit="kg",
                waste_count=5,
                percentage_of_total=39.22,
            )
        ],
        waste_by_category=[
            WasteByCategory(
                category="vegetable",
                total_quantity=Decimal("15.0"),
                waste_count=7,
                percentage_of_total=58.82,
            )
        ],
        waste_trends=[
            WasteTrend(
                period="2025-W44",
                total_quantity=Decimal("25.5"),
                waste_count=10,
            )
        ],
        common_reasons=[
            {"reason": "expired", "count": 6},
            {"reason": "spoiled", "count": 4},
        ],
        horizon_days=30,
    )

    def fake_build_insights(db, uid, horizon_days):
        return mock_insights

    monkeypatch.setattr(WasteService, "build_insights", fake_build_insights)

    r = client.get(f"/waste/insights?user_id={user_id}&horizon=30")

    assert r.status_code == 200
    body = r.json()
    assert body["total_waste_count"] == 10
    assert float(body["total_quantity"]) == 25.5
    assert body["horizon_days"] == 30
    assert len(body["most_wasted_ingredients"]) == 1
    assert len(body["waste_by_category"]) == 1
    assert len(body["waste_trends"]) == 1
    assert len(body["common_reasons"]) == 2


def test_get_waste_insights_user_not_found(monkeypatch):
    """Test waste insights when user not found"""
    user_id = uuid.uuid4()

    def fake_build_insights_error(db, uid, horizon_days):
        raise NotFoundError(f"User {uid} not found")

    monkeypatch.setattr(WasteService, "build_insights", fake_build_insights_error)

    r = client.get(f"/waste/insights?user_id={user_id}&horizon=30")

    assert r.status_code == 404


def test_get_waste_insights_default_horizon(monkeypatch):
    """Test waste insights with default horizon parameter"""
    user_id = uuid.uuid4()

    from domain.schemas.waste_schemas import (
        WasteByIngredient,
        WasteByCategory,
        WasteTrend,
    )

    mock_insights = WasteInsightsResponse(
        total_waste_count=0,
        total_quantity=Decimal("0"),
        most_wasted_ingredients=[],
        waste_by_category=[],
        waste_trends=[],
        common_reasons=[],
        horizon_days=30,
    )

    def fake_build_insights(db, uid, horizon_days):
        assert horizon_days == 30  # Verify default is used
        return mock_insights

    monkeypatch.setattr(WasteService, "build_insights", fake_build_insights)

    # Call without specifying horizon
    r = client.get(f"/waste/insights?user_id={user_id}")

    assert r.status_code == 200
    body = r.json()
    assert body["horizon_days"] == 30


# ========== New Feature Tests ==========


def test_update_pantry_quantity_consume(monkeypatch):
    """Test consuming/decrementing pantry item quantity"""
    item = make_pantry_item()
    item.quantity = Decimal("2.0")

    # After consuming 0.5, should have 1.5 left
    updated_item = make_pantry_item(pantry_item_id=item.pantry_item_id)
    updated_item.quantity = Decimal("1.5")

    monkeypatch.setattr(
        PantryService,
        "update_quantity",
        lambda db, pid, qc, reason: updated_item,
    )

    r = client.patch(
        f"/pantry/{item.pantry_item_id}",
        json={"quantity_change": -0.5, "reason": "cooking"},
    )

    assert r.status_code == 200
    body = r.json()
    assert float(body["quantity"]) == 1.5


def test_update_pantry_quantity_add(monkeypatch):
    """Test adding to pantry item quantity"""
    item = make_pantry_item()
    item.quantity = Decimal("1.0")

    # After adding 2, should have 3
    updated_item = make_pantry_item(pantry_item_id=item.pantry_item_id)
    updated_item.quantity = Decimal("3.0")

    monkeypatch.setattr(
        PantryService, "update_quantity", lambda db, pid, qc, reason: updated_item
    )

    r = client.patch(
        f"/pantry/{item.pantry_item_id}",
        json={"quantity_change": 2.0, "reason": "found_more"},
    )

    assert r.status_code == 200
    body = r.json()
    assert float(body["quantity"]) == 3.0


def test_update_pantry_quantity_not_found(monkeypatch):
    """Test updating non-existent pantry item"""

    def raise_not_found(db, pid, qc, reason):
        raise NotFoundError(f"Pantry item {pid} not found")

    monkeypatch.setattr(PantryService, "update_quantity", raise_not_found)

    r = client.patch(
        f"/pantry/{uuid.uuid4()}", json={"quantity_change": -0.5, "reason": "cooking"}
    )

    assert r.status_code == 404


def test_get_expiring_soon(monkeypatch):
    """Test getting items expiring within threshold"""
    user = make_user()

    # Create items with different expiry dates
    item1 = make_pantry_item(user_id=user.user_id)
    item1.best_before = datetime.utcnow().date()
    item1.ingredient_id = uuid.uuid4()

    item2 = make_pantry_item(user_id=user.user_id)
    from datetime import timedelta

    item2.best_before = datetime.utcnow().date() + timedelta(days=2)
    item2.ingredient_id = uuid.uuid4()

    monkeypatch.setattr(
        PantryService, "get_expiring_soon", lambda db, uid, days: [item1, item2]
    )

    r = client.get(f"/pantry/expiring-soon?user_id={user.user_id}&days=3")

    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    # Should be ordered by expiry (oldest first)


def test_waste_log_with_pantry_integration(monkeypatch):
    """Test logging waste with automatic pantry update"""
    user = make_user()
    pantry_item_id = uuid.uuid4()

    def fake_validate(iid, qty, unit):
        return {
            "ingredient_id": iid,
            "quantity": qty,
            "unit": unit,
            "ingredient_name": "Test Ingredient",
            "category": "vegetable",
        }

    def fake_log_waste(db, uid, waste_data):
        # Should receive pantry integration data
        assert waste_data.pantry_item_id == pantry_item_id
        assert waste_data.auto_remove_from_pantry == True

        return SimpleNamespace(
            waste_id=uuid.uuid4(),
            user_id=uid,
            ingredient_id=waste_data.ingredient_id,
            quantity=waste_data.quantity,
            unit=waste_data.unit,
            reason=waste_data.reason,
            occurred_at=datetime.utcnow(),
        )

    monkeypatch.setattr(WasteService, "validate_waste_data", fake_validate)
    monkeypatch.setattr(WasteService, "log_waste", fake_log_waste)

    r = client.post(
        f"/waste?user_id={user.user_id}",
        json={
            "ingredient_id": str(uuid.uuid4()),
            "quantity": 0.5,
            "unit": "kg",
            "reason": "spoiled",
            "pantry_item_id": str(pantry_item_id),
            "auto_remove_from_pantry": True,
        },
    )

    assert r.status_code == 201


# ========== Recipe Recommendation Tests (Use Case 7) ==========

def test_recommendations_endpoint(monkeypatch):
    """Test the recommendation endpoint (Use Case 7)."""
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
                {"ingredient_id": str(uuid.uuid4()), "name": "tofu", "quantity": 400, "unit": "g"}
            ],
            "steps": [
                {"order": 1, "text": "Cook tofu", "duration_min": 10}
            ],
            "cuisine_id": "asian-cuisine-id",
            "match_score": 80.0,
            "pantry_match_count": 0
        },
        {
            "_id": "recipe-uuid-2",
            "title": "Quick Salad",
            "slug": "quick-salad",
            "tags": ["vegetarian", "quick", "healthy"],
            "yields": {"servings": 2, "serving_unit": "servings"},
            "ingredients": [
                {"ingredient_id": str(uuid.uuid4()), "name": "lettuce", "quantity": 200, "unit": "g"}
            ],
            "steps": [
                {"order": 1, "text": "Toss salad", "duration_min": 5}
            ],
            "cuisine_id": "american-cuisine-id",
            "match_score": 70.0,
            "pantry_match_count": 0
        }
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
