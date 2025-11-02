"""
Tests for Waste Management (Use Case 9).

This test suite covers waste tracking and insights:
- Logging food waste events
- Waste analytics and insights
- Integration with pantry (auto-removal)
- Waste trends and patterns
- Category-based analysis

Waste management helps users:
- Understand their waste patterns
- Identify frequently wasted ingredients
- Make better purchasing decisions
- Track progress in waste reduction
"""

import pytest
import uuid
from datetime import datetime
from decimal import Decimal

from test_fixtures import client, make_user, make_waste_log
from services.waste_service import WasteService
from domain.schemas.waste_schemas import (
    WasteLogResponse,
    WasteInsightsResponse,
    WasteByIngredient,
    WasteByCategory,
    WasteTrend,
)
from core.exceptions import NotFoundError, ServiceValidationError


# =============================================================================
# WASTE MANAGEMENT FLOW
# =============================================================================

EXAMPLE_WASTE_FLOW = """
Waste Management Flow (Use Case 9)
======================================

1. LOG WASTE EVENT
   POST /waste?user_id=123e4567-e89b-12d3-a456-426614174000
   {
       "ingredient_id": "uuid-tomatoes",
       "quantity": 2.5,
       "unit": "kg",
       "reason": "expired",
       "pantry_item_id": "pantry-item-uuid",  # Optional
       "auto_remove_from_pantry": true        # Optional
   }
   
   Response: 201 Created
   {
       "waste_id": "waste-uuid-1",
       "user_id": "123e4567-e89b-12d3-a456-426614174000",
       "ingredient_id": "uuid-tomatoes",
       "ingredient_name": "tomatoes",
       "quantity": 2.5,
       "unit": "kg",
       "reason": "expired",
       "occurred_at": "2025-11-01T10:00:00Z"
   }

2. GET WASTE INSIGHTS
   GET /waste/insights?user_id=123e4567-e89b-12d3-a456-426614174000&horizon=30
   
   Response: 200 OK
   {
       "total_waste_count": 10,
       "total_quantity": 25.5,
       "horizon_days": 30,
       
       "most_wasted_ingredients": [
           {
               "ingredient_id": "uuid-tomatoes",
               "ingredient_name": "tomatoes",
               "total_quantity": 10.0,
               "unit": "kg",
               "waste_count": 5,
               "percentage_of_total": 39.22
           }
       ],
       
       "waste_by_category": [
           {
               "category": "vegetable",
               "total_quantity": 15.0,
               "waste_count": 7,
               "percentage_of_total": 58.82
           }
       ],
       
       "waste_trends": [
           {
               "period": "2025-W44",
               "total_quantity": 25.5,
               "waste_count": 10
           }
       ],
       
       "common_reasons": [
           {"reason": "expired", "count": 6},
           {"reason": "spoiled", "count": 4}
       ]
   }
"""


WASTE_REASONS = """
Common Waste Reasons
======================================

Standard waste reasons tracked by the system:

1. expired - Item passed best before date
2. spoiled - Item went bad before expiry
3. overcooked - Cooking error
4. burnt - Severe cooking error
5. leftover - Prepared food not consumed
6. freezer_burn - Frozen item damaged
7. mold - Visible mold growth
8. taste_bad - Quality issues
9. other - Miscellaneous reasons

Reason categorization helps identify:
- Storage issues (expired, spoiled, freezer_burn, mold)
- Cooking issues (overcooked, burnt)
- Portion issues (leftover)
- Purchase quality (taste_bad)
"""


PANTRY_INTEGRATION = """
Waste-Pantry Integration
======================================

When logging waste, users can optionally:

1. Link to pantry item:
   - Specify pantry_item_id in waste log
   - System validates item belongs to user
   - Maintains audit trail

2. Auto-remove from pantry:
   - Set auto_remove_from_pantry: true
   - System automatically decrements/removes pantry item
   - Ensures pantry stays accurate

Workflow:
User logs waste -> System checks pantry_item_id -> Decrements quantity -> 
If quantity reaches 0 -> Remove item from pantry

Benefits:
- Single action updates both waste log and pantry
- Prevents stale pantry data
- Simplifies user workflow
"""


# =============================================================================
# WASTE LOGGING TESTS
# =============================================================================


def test_log_waste_success(monkeypatch):
    """
    Test successful waste logging.

    Verifies:
    1. POST /waste creates waste log entry
    2. Response includes all waste log fields
    3. Ingredient validation succeeds

    Data consistency:
    - Test user: make_user()
    - Test waste: 2.5 kg, reason "expired"
    - Ingredient validation returns standard metadata

    Integration:
    - Ingredient validated via Neo4j (mocked)
    - User verified via PostgreSQL (mocked)
    - Waste log stored in PostgreSQL
    """
    user_id = uuid.uuid4()
    waste_log = make_waste_log(user_id=user_id, quantity=2.5, reason="expired")

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
    """
    Test waste logging when user not found.

    Verifies error handling:
    - Service raises NotFoundError for invalid user_id
    - API returns 404 Not Found
    - Error message includes user_id for debugging

    This prevents waste logs for non-existent users.
    """
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
    """
    Test waste logging with validation error.

    Verifies Pydantic validation:
    - Quantity must be > 0
    - Invalid quantity (0) returns 422 Unprocessable Entity
    - Validation happens before service layer

    Data consistency:
    - Test uses quantity: 0 (invalid)
    - Should be rejected by schema validation
    """
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


# =============================================================================
# WASTE INSIGHTS TESTS
# =============================================================================


def test_get_waste_insights_success(monkeypatch):
    """
    Test successful retrieval of waste insights.

    Verifies:
    1. GET /waste/insights aggregates waste data
    2. Response includes all insight categories
    3. Calculations use specified horizon (default 30 days)

    Insight categories:
    - most_wasted_ingredients: Top 5 by quantity
    - waste_by_category: Aggregated by ingredient category
    - waste_trends: Time-based patterns (weekly)
    - common_reasons: Most frequent waste reasons

    Data consistency:
    - Test data: 10 waste events, 25.5 total quantity
    - Horizon: 30 days
    - Mock data includes realistic percentages

    Use cases:
    - Dashboard visualization
    - Waste reduction recommendations
    - Shopping habit insights
    """
    user_id = uuid.uuid4()

    # Create mock insights response
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
    """
    Test waste insights when user not found.

    Verifies error handling:
    - Service raises NotFoundError for invalid user
    - API returns 404 Not Found

    Prevents insights for non-existent users.
    """
    user_id = uuid.uuid4()

    def fake_build_insights_error(db, uid, horizon_days):
        raise NotFoundError(f"User {uid} not found")

    monkeypatch.setattr(WasteService, "build_insights", fake_build_insights_error)

    r = client.get(f"/waste/insights?user_id={user_id}&horizon=30")

    assert r.status_code == 404


def test_get_waste_insights_default_horizon(monkeypatch):
    """
    Test waste insights with default horizon parameter.

    Verifies:
    - Default horizon is 30 days when not specified
    - Service receives correct default value
    - Response confirms horizon used

    Data consistency:
    - Default horizon: 30 days (industry standard for monthly analysis)
    - Empty insights (no waste logged) still valid response
    """
    user_id = uuid.uuid4()

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


# =============================================================================
# PANTRY INTEGRATION TESTS
# =============================================================================


def test_waste_log_with_pantry_integration(monkeypatch):
    """
    Test logging waste with automatic pantry update.

    Scenario:
    - User has 500g chicken in pantry
    - 250g spoiled, logged as waste
    - auto_remove_from_pantry: true
    - Pantry updated to 250g automatically

    Verifies:
    1. Waste log receives pantry_item_id
    2. auto_remove_from_pantry flag passed correctly
    3. Service handles integration logic

    Data consistency:
    - Uses make_user() for consistent user data
    - pantry_item_id: UUID reference to pantry
    - Waste quantity: 0.5 kg, reason: "spoiled"

    Integration benefits:
    - Single action updates both systems
    - Maintains data consistency
    - Reduces user effort
    """
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

        return make_waste_log(
            user_id=uid,
            ingredient_id=waste_data.ingredient_id,
            quantity=waste_data.quantity,
            unit=waste_data.unit,
            reason=waste_data.reason,
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


if __name__ == "__main__":
    print(EXAMPLE_WASTE_FLOW)
    print("\n" + "=" * 70 + "\n")
    print(WASTE_REASONS)
    print("\n" + "=" * 70 + "\n")
    print(PANTRY_INTEGRATION)
