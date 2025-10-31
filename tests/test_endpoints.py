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
import core.database.models as db_models

db_models.init_database = lambda: None

# Restore original create_engine in case other imports need it
if _real_create_engine is not None:
    sqlalchemy.create_engine = _real_create_engine

from fastapi.testclient import TestClient
import pytest

from main import app
from core.services import profile_service, pantry_service
from core.schemas.profile_schemas import PantryItemCreate
from core.exceptions import ServiceValidationError

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

    monkeypatch.setattr(
        profile_service.ProfileService, "get_all_users", lambda db: [user]
    )
    r = client.get("/users")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # create_user
    created = make_user()

    def fake_create(db, email, full_name=None):
        return created

    monkeypatch.setattr(profile_service.ProfileService, "create_user", fake_create)
    r2 = client.post("/users", json={"email": "a@b.com", "full_name": "A B"})
    assert r2.status_code == 201
    assert r2.json()["email"] == created.email

    # get_profile
    monkeypatch.setattr(
        profile_service.ProfileService, "get_user_profile", lambda db, uid: user
    )
    r3 = client.get(f"/users/{user.user_id}")
    assert r3.status_code == 200
    assert r3.json()["user_id"] == str(user.user_id)

    # delete
    monkeypatch.setattr(
        profile_service.ProfileService, "delete_user", lambda db, uid: True
    )
    r4 = client.delete(f"/users/{user.user_id}")
    assert r4.status_code == 200
    assert r4.json()["deleted"] == str(user.user_id)


def test_update_profile(monkeypatch):
    user = make_user()
    def fake_upsert(db, uid, profile_data):
        # mimic new service signature returning (user, created_flag)
        return user, False

    monkeypatch.setattr(profile_service.ProfileService, "upsert_profile", fake_upsert)
    payload = {"full_name": "Updated"}
    r = client.put(f"/users/{user.user_id}", json=payload)
    assert r.status_code == 200
    assert r.json()["full_name"] == user.full_name


def test_update_profile_create_on_put(monkeypatch):
    # When the service indicates a creation happened, route should return 201 and Location header
    created_user = make_user()

    def fake_upsert_created(db, uid, profile_data):
        return created_user, True

    monkeypatch.setattr(profile_service.ProfileService, "upsert_profile", fake_upsert_created)
    payload = {"full_name": "New User", "email": "new@example.com"}
    r = client.put(f"/users/{created_user.user_id}", json=payload)
    assert r.status_code == 201
    # Location header should be set to new resource
    assert r.headers.get("location") == f"/users/{created_user.user_id}"
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
    monkeypatch.setattr(
        profile_service.ProfileService, "get_dietary_profile", lambda db, uid: dp
    )
    r = client.get(f"/users/{user.user_id}/dietary")
    assert r.status_code == 200
    assert r.json()["kcal_target"] == dp.kcal_target

    monkeypatch.setattr(
        profile_service.ProfileService, "set_dietary_profile", lambda db, uid, p: dp
    )
    payload = {"goal": "maintenance", "activity": "moderate", "kcal_target": 2000}
    r2 = client.put(f"/users/{user.user_id}/dietary", json=payload)
    assert r2.status_code == 200
    assert r2.json()["goal"] == dp.goal


def test_preferences_bulk_and_single(monkeypatch):
    user = make_user()
    pref = SimpleNamespace(tag="vegan", strength="like")
    monkeypatch.setattr(
        profile_service.ProfileService, "get_preferences", lambda db, uid: [pref]
    )
    r = client.get(f"/users/{user.user_id}/preferences")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    monkeypatch.setattr(
        profile_service.ProfileService, "set_preferences", lambda db, uid, prefs: [pref]
    )
    r2 = client.put(
        f"/users/{user.user_id}/preferences",
        json=[{"tag": "vegan", "strength": "like"}],
    )
    assert r2.status_code == 200

    monkeypatch.setattr(
        profile_service.ProfileService, "add_preference", lambda db, uid, p: pref
    )
    r3 = client.post(
        f"/users/{user.user_id}/preferences", json={"tag": "vegan", "strength": "like"}
    )
    assert r3.status_code == 201

    monkeypatch.setattr(
        profile_service.ProfileService, "remove_preference", lambda db, uid, tag: True
    )
    r4 = client.delete(f"/users/{user.user_id}/preferences/vegan")
    assert r4.status_code == 200


def test_allergies_bulk_and_single(monkeypatch):
    user = make_user()
    allergy = SimpleNamespace(ingredient_id=uuid.uuid4(), note="nuts")
    monkeypatch.setattr(
        profile_service.ProfileService, "get_allergies", lambda db, uid: [allergy]
    )
    r = client.get(f"/users/{user.user_id}/allergies")
    assert r.status_code == 200

    monkeypatch.setattr(
        profile_service.ProfileService, "set_allergies", lambda db, uid, a: [allergy]
    )
    r2 = client.put(
        f"/users/{user.user_id}/allergies",
        json=[{"ingredient_id": str(allergy.ingredient_id), "note": "nuts"}],
    )
    assert r2.status_code == 200

    monkeypatch.setattr(
        profile_service.ProfileService, "add_allergy", lambda db, uid, a: allergy
    )
    r3 = client.post(
        f"/users/{user.user_id}/allergies",
        json={"ingredient_id": str(allergy.ingredient_id), "note": "nuts"},
    )
    assert r3.status_code == 201

    monkeypatch.setattr(
        profile_service.ProfileService, "remove_allergy", lambda db, uid, iid: True
    )
    r4 = client.delete(f"/users/{user.user_id}/allergies/{allergy.ingredient_id}")
    assert r4.status_code == 200


def test_pantry_endpoints(monkeypatch):
    user = make_user()
    item = make_pantry_item(user_id=user.user_id)

    monkeypatch.setattr(
        pantry_service.PantryService, "get_pantry", lambda db, uid: [item]
    )
    r = client.get(f"/pantry?user_id={user.user_id}")
    assert r.status_code == 200

    monkeypatch.setattr(
        pantry_service.PantryService, "set_pantry", lambda db, uid, items: [item]
    )
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

    monkeypatch.setattr(
        pantry_service.PantryService, "add_item", lambda db, uid, it: item
    )
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

    monkeypatch.setattr(
        pantry_service.PantryService, "remove_item", lambda db, pid: True
    )
    r4 = client.delete(f"/pantry/{item.pantry_item_id}")
    assert r4.status_code == 200


def test_update_profile_service_error(monkeypatch):
    user = make_user()

    def fake_upsert_error(db, uid, profile_data):
        raise ServiceValidationError("User not found")

    monkeypatch.setattr(profile_service.ProfileService, "upsert_profile", fake_upsert_error)
    r = client.put(f"/users/{user.user_id}", json={"full_name": "X"})
    assert r.status_code == 400


def test_pantry_quantity_validation_and_response(monkeypatch):
    # Validation: quantity must be > 0
    user = make_user()
    item = make_pantry_item(user_id=user.user_id)

    # invalid quantity -> 422 from FastAPI/Pydantic
    r = client.post(
        "/pantry",
        json={
            "user_id": str(user.user_id),
            "item": {"ingredient_id": str(item.ingredient_id), "quantity": 0, "unit": "pcs"},
        },
    )
    assert r.status_code == 422

    # valid quantity -> use monkeypatched service to return an item and assert body
    returned = make_pantry_item(user_id=user.user_id)
    returned.quantity = 3.5
    returned.best_before = datetime.utcnow().date()

    monkeypatch.setattr(pantry_service.PantryService, "add_item", lambda db, uid, it: returned)
    r2 = client.post(
        "/pantry",
        json={
            "user_id": str(user.user_id),
            "item": {"ingredient_id": str(item.ingredient_id), "quantity": 3.5, "unit": "pcs"},
        },
    )
    assert r2.status_code == 201
    body = r2.json()
    assert float(body["quantity"]) == 3.5
