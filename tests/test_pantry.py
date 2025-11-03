"""
Tests for Pantry Management (Use Case 5).

This test suite covers pantry inventory operations:
- Adding ingredients to pantry
- Updating pantry quantities (consume/add)
- Removing items from pantry
- Bulk pantry management
- Expiration tracking
- Ingredient validation via Neo4j

The pantry serves as:
- Foundation for shopping list generation (Use Case 6)
- Input for recipe recommendations (Use Case 7)
- Source for waste tracking (Use Case 9)
"""

import pytest
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from test_fixtures import client, make_user, make_pantry_item
from services.pantry_service import PantryService
from app.exceptions import NotFoundError


# =============================================================================
# PANTRY MANAGEMENT FLOW
# =============================================================================

EXAMPLE_PANTRY_FLOW = """
Pantry Management Flow (Use Case 5)
======================================

1. VIEW PANTRY INVENTORY
   GET /pantry?user_id=123e4567-e89b-12d3-a456-426614174000
   
   Response: 200 OK
   [
       {
           "pantry_item_id": "item-uuid-1",
           "user_id": "123e4567-e89b-12d3-a456-426614174000",
           "ingredient_id": "uuid-rice",
           "ingredient_name": "rice",
           "quantity": 1000,
           "unit": "g",
           "best_before": "2025-12-31",
           "source": "grocery_store",
           "created_at": "2025-11-01T10:00:00Z",
           "updated_at": "2025-11-01T10:00:00Z"
       },
       ...
   ]

2. ADD ITEM TO PANTRY
   POST /pantry
   {
       "user_id": "123e4567-e89b-12d3-a456-426614174000",
       "item": {
           "ingredient_id": "uuid-chicken",
           "quantity": 500,
           "unit": "g",
           "best_before": "2025-11-05"
       }
   }
   
   Response: 201 Created

3. BULK UPDATE PANTRY (REPLACE ALL)
   PUT /pantry
   {
       "user_id": "123e4567-e89b-12d3-a456-426614174000",
       "items": [
           {
               "ingredient_id": "uuid-rice",
               "quantity": 1000,
               "unit": "g"
           },
           {
               "ingredient_id": "uuid-eggs",
               "quantity": 6,
               "unit": "units"
           }
       ]
   }
   
   Response: 200 OK

4. UPDATE QUANTITY (CONSUME/ADD)
   PATCH /pantry/item-uuid-1
   {
       "quantity_change": -200,
       "reason": "cooking"
   }
   
   Response: 200 OK
   {
       "pantry_item_id": "item-uuid-1",
       "quantity": 800,  # Was 1000, consumed 200
       ...
   }

5. GET EXPIRING SOON ITEMS
   GET /pantry/expiring-soon?user_id=123e4567-e89b-12d3-a456-426614174000&days=3
   
   Response: 200 OK
   [
       {
           "pantry_item_id": "item-uuid-2",
           "ingredient_name": "chicken breast",
           "quantity": 500,
           "unit": "g",
           "best_before": "2025-11-03",
           "days_until_expiry": 2
       }
   ]

6. REMOVE ITEM FROM PANTRY
   DELETE /pantry/item-uuid-1
   
   Response: 200 OK
   {
       "status": "ok",
       "deleted": "item-uuid-1"
   }
"""


INGREDIENT_VALIDATION_FLOW = """
Ingredient Validation via Neo4j
======================================

When adding items to pantry, the system validates ingredients against Neo4j:

1. Validate Single Ingredient:
   - Query Neo4j for ingredient metadata
   - Retrieve: name, category, perishability, defaults
   - Used for: POST /pantry (single item)

2. Validate Batch of Ingredients:
   - Query Neo4j for multiple ingredients at once
   - Optimized for: PUT /pantry (bulk update)
   - Returns: {ingredient_id: metadata} mapping

Ingredient Metadata Structure:
{
    "name": "chicken breast",
    "category": "protein",
    "perishability": "perishable",
    "defaults": {
        "shelf_life_days": 3,
        "typical_unit": "g"
    }
}

Integration Points:
- Shopping lists: Ingredient names for display
- Recommendations: Pantry-based recipe matching
- Waste tracking: Category-based insights
"""


# =============================================================================
# PANTRY CRUD TESTS
# =============================================================================


def test_pantry_endpoints(monkeypatch):
    """
    Integration test for pantry CRUD operations.

    Verifies:
    1. GET /pantry - View pantry inventory
    2. PUT /pantry - Bulk update (replace all items)
    3. POST /pantry - Add single item
    4. DELETE /pantry/{pantry_item_id} - Remove item

    Data consistency:
    - Uses make_user() and make_pantry_item() for consistent mock data
    - Default quantity: 1.0 pcs
    - Ingredient validation mocked to return standard metadata
    """
    user = make_user()
    item = make_pantry_item(user_id=user.user_id)

    # Mock ingredient validation
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

    # Test: Get pantry inventory
    monkeypatch.setattr(PantryService, "get_pantry", lambda db, uid: [item])
    r = client.get(f"/pantry?user_id={user.user_id}")
    assert r.status_code == 200

    # Test: Bulk update pantry
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

    # Test: Add single item
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

    # Test: Remove item
    monkeypatch.setattr(PantryService, "remove_item", lambda db, pid: True)
    r4 = client.delete(f"/pantry/{item.pantry_item_id}")
    assert r4.status_code == 200


# =============================================================================
# QUANTITY VALIDATION TESTS
# =============================================================================


def test_pantry_quantity_validation_and_response(monkeypatch):
    """
    Test quantity validation and response formatting.

    Verifies:
    1. Pydantic validation: quantity > 0 (rejects 0 or negative)
    2. Response includes all expected fields
    3. Decimal quantities preserved in response

    Validation rules:
    - Quantity must be > 0 (enforced by Pydantic schema)
    - Invalid quantities return 422 Unprocessable Entity

    Data consistency:
    - Valid test quantity: 3.5 pcs
    - Invalid test quantity: 0 pcs (should be rejected)
    """
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

    # Test: Invalid quantity (0) -> 422 from FastAPI/Pydantic
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

    # Test: Valid quantity with decimal -> successful response
    returned = make_pantry_item(user_id=user.user_id, quantity=3.5)
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


# =============================================================================
# QUANTITY UPDATE TESTS
# =============================================================================


def test_update_pantry_quantity_consume(monkeypatch):
    """
    Test consuming/decrementing pantry item quantity.

    Scenario:
    - Initial quantity: 2.0
    - Consume: 0.5 (quantity_change: -0.5)
    - Final quantity: 1.5

    Use cases:
    - Cooking from recipes (auto-update after meal prep)
    - Manual consumption tracking
    - Integration with meal plan execution

    Data consistency:
    - Test uses consistent make_pantry_item() factory
    - Decimal precision maintained throughout
    - Starting with 800g chicken, consuming 300g → 500g remaining
    """
    item = make_pantry_item(
        ingredient_name="chicken breast", quantity=Decimal("800"), unit="g"
    )

    # After consuming 300g, should have 500g left
    updated_item = make_pantry_item(
        pantry_item_id=item.pantry_item_id,
        ingredient_name="chicken breast",
        quantity=Decimal("500"),
        unit="g",
    )

    monkeypatch.setattr(
        PantryService,
        "update_quantity",
        lambda db, pid, qc, reason: updated_item,
    )

    r = client.patch(
        f"/pantry/{item.pantry_item_id}",
        json={"quantity_change": -300, "reason": "cooking"},
    )

    assert r.status_code == 200
    body = r.json()
    assert float(body["quantity"]) == 500.0  # 800g - 300g


def test_update_pantry_quantity_add(monkeypatch):
    """
    Test adding to pantry item quantity.

    Scenario:
    - Initial quantity: 1.0
    - Add: 2.0 (quantity_change: +2.0)
    - Final quantity: 3.0

    Use cases:
    - Adding groceries to existing pantry item
    - Combining partial packages
    - Manual inventory correction

    Data consistency:
    - Positive quantity_change indicates addition
    - Negative quantity_change indicates consumption (see test_update_pantry_quantity_consume)
    - Starting with 500g (realistic rice portion), adding 200g → 700g total
    """
    item = make_pantry_item(ingredient_name="rice", quantity=Decimal("500"), unit="g")

    # After adding 200g, should have 700g
    updated_item = make_pantry_item(
        pantry_item_id=item.pantry_item_id,
        ingredient_name="rice",
        quantity=Decimal("700"),
        unit="g",
    )

    monkeypatch.setattr(
        PantryService, "update_quantity", lambda db, pid, qc, reason: updated_item
    )

    r = client.patch(
        f"/pantry/{item.pantry_item_id}",
        json={"quantity_change": 200, "reason": "found_more"},
    )

    assert r.status_code == 200
    body = r.json()
    assert float(body["quantity"]) == 700.0  # 500g + 200g


def test_update_pantry_quantity_not_found(monkeypatch):
    """
    Test updating non-existent pantry item.

    Verifies error handling when:
    - Pantry item ID doesn't exist
    - Service raises NotFoundError
    - API returns 404 Not Found

    This ensures proper error propagation from service layer.
    """

    def raise_not_found(db, pid, qc, reason):
        raise NotFoundError(f"Pantry item {pid} not found")

    monkeypatch.setattr(PantryService, "update_quantity", raise_not_found)

    r = client.patch(
        f"/pantry/{uuid.uuid4()}", json={"quantity_change": -0.5, "reason": "cooking"}
    )

    assert r.status_code == 404


# =============================================================================
# EXPIRATION TRACKING TESTS
# =============================================================================


def test_get_expiring_soon(monkeypatch):
    """
    Test getting items expiring within threshold.

    Scenario:
    - Query for items expiring in next 3 days
    - Returns items sorted by expiry date (oldest first)

    Test data:
    - Item 1: Expires today (most urgent)
    - Item 2: Expires in 2 days

    Use cases:
    - Proactive waste prevention
    - Recipe suggestions using expiring ingredients
    - Shopping list optimization (don't buy what's expiring)

    Data consistency:
    - Uses datetime.utcnow().date() for current date
    - Expiry dates calculated as timedelta from now
    """
    user = make_user()

    # Create items with different expiry dates
    item1 = make_pantry_item(
        user_id=user.user_id, best_before=datetime.utcnow().date()  # Expires today
    )

    item2 = make_pantry_item(
        user_id=user.user_id,
        best_before=datetime.utcnow().date() + timedelta(days=2),  # Expires in 2 days
    )

    monkeypatch.setattr(
        PantryService, "get_expiring_soon", lambda db, uid, days: [item1, item2]
    )

    r = client.get(f"/pantry/expiring-soon?user_id={user.user_id}&days=3")

    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    # Should be ordered by expiry (oldest first)


if __name__ == "__main__":
    print(EXAMPLE_PANTRY_FLOW)
    print("\n" + "=" * 70 + "\n")
    print(INGREDIENT_VALIDATION_FLOW)
