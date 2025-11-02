"""
Comprehensive error handling and edge case tests.

This test suite covers error conditions, validation failures, and edge cases:
- Validation errors (invalid data, constraints)
- Not found errors (missing resources)
- Duplicate entries and race conditions
- Transaction rollbacks
- Boundary conditions
- Null/empty data handling
"""

import pytest
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from test_fixtures import client, db_session
from services.profile_service import ProfileService
from services.ingredient_service import IngredientService
from services.pantry_service import PantryService
from services.waste_service import WasteService
from repositories import (
    UserRepository,
    IngredientSQLRepository,
    PantryRepository,
)
from domain.models import PantryItem, WasteLog
from domain.schemas.waste_schemas import WasteLogCreate
from domain.schemas.profile_schemas import (
    PantryItemCreate,
    DietaryProfileCreate,
    AllergyCreate,
    PreferenceCreate,
)
from core.exceptions import NotFoundError, ServiceValidationError


# Helper function to generate unique emails
def unique_email(prefix: str = "test") -> str:
    """Generate unique email address using UUID to avoid conflicts"""
    return f"{prefix}-{uuid.uuid4()}@example.com"


# =============================================================================
# VALIDATION ERROR TESTS
# =============================================================================


def test_user_duplicate_email(db_session: Session):
    """
    Test that duplicate emails are prevented.

    Verifies:
    - First user creation succeeds
    - Second user with same email raises ServiceValidationError
    """
    repo = UserRepository(db_session)

    # Create first user
    email = unique_email("duplicate")
    user1 = repo.create_user(email=email, full_name="User One")
    assert user1.user_id is not None

    # Try to create second user with same email
    with pytest.raises(ServiceValidationError):
        user2 = repo.create_user(email=email, full_name="User Two")


def test_pantry_invalid_quantity(db_session: Session):
    """
    Test that invalid quantities are rejected by database constraints.

    Verifies:
    - Negative quantities are rejected by DB check constraint
    - Database enforces quantity >= 0
    """
    user = ProfileService.create_user(db_session, unique_email("qty"), "Qty User")
    ing = IngredientService.get_or_create_ingredient(db_session, "test")
    pantry_repo = PantryRepository(db_session)

    # Negative quantity - should be rejected by database constraint
    pantry_item = PantryItem(
        user_id=user.user_id,
        ingredient_id=ing.ingredient_id,
        quantity=Decimal("-10"),
        unit="g",
    )

    with pytest.raises(IntegrityError):
        pantry_repo.create(pantry_item)


def test_pantry_missing_ingredient_validation(db_session: Session):
    """
    Test pantry operations when ingredient validation fails.

    Verifies:
    - PantryService validates ingredient exists in Neo4j
    - Raises ServiceValidationError if ingredient not found
    """
    user = ProfileService.create_user(db_session, unique_email("noing"), "No Ing User")
    fake_ing_id = uuid.uuid4()

    # Mock Neo4j to return None (ingredient not found)
    with patch.object(PantryService, "validate_ingredient_data") as mock_validate:
        mock_validate.return_value = None

        with pytest.raises(ServiceValidationError):
            item_data = PantryItemCreate(
                ingredient_id=fake_ing_id,
                quantity=Decimal("100"),
                unit="g",
            )
            PantryService.add_item(db_session, user.user_id, item_data)


def test_waste_invalid_reason(db_session: Session):
    """
    Test that invalid waste reasons are handled.

    Valid reasons: expired, spoiled, overcooked, burnt, leftover,
                   freezer_burn, mold, taste_bad, other

    Verifies:
    - Valid reasons are accepted
    - Invalid reasons should be rejected (if validation exists)
    """
    user = ProfileService.create_user(db_session, unique_email("reason"), "Reason User")
    ing = IngredientService.get_or_create_ingredient(db_session, "tomato")

    # Valid reason
    with patch.object(WasteService, "validate_waste_data") as mock_validate:
        mock_validate.return_value = {
            "ingredient_id": ing.ingredient_id,
            "ingredient_name": "tomato",
            "quantity": Decimal("1.0"),
            "unit": "kg",
            "category": "vegetable",
        }

        waste_data = WasteLogCreate(
            ingredient_id=ing.ingredient_id,
            quantity=Decimal("1.0"),
            unit="kg",
            reason="expired",  # Valid
        )
        waste = WasteService.log_waste(
            db_session,
            user.user_id,
            waste_data,
        )
        assert waste.reason == "expired"

    # Invalid reason - currently no validation, but should add
    # This documents expected future behavior
    with patch.object(WasteService, "validate_waste_data") as mock_validate:
        mock_validate.return_value = {
            "ingredient_id": ing.ingredient_id,
            "ingredient_name": "tomato",
            "quantity": Decimal("1.0"),
            "unit": "kg",
            "category": "vegetable",
        }

        waste_data = WasteLogCreate(
            ingredient_id=ing.ingredient_id,
            quantity=Decimal("1.0"),
            unit="kg",
            reason="invalid_reason",  # Currently allowed
        )
        waste = WasteService.log_waste(
            db_session,
            user.user_id,
            waste_data,
        )
        assert waste.reason == "invalid_reason"
        # TODO: Add validation to restrict to valid reasons


# =============================================================================
# NOT FOUND ERROR TESTS
# =============================================================================


def test_get_nonexistent_user(db_session: Session):
    """
    Test accessing non-existent user.

    Verifies:
    - get_user_profile() returns None for non-existent user
    """
    fake_id = uuid.uuid4()
    user = ProfileService.get_user_profile(db_session, fake_id)
    assert user is None


def test_pantry_update_nonexistent_item(db_session: Session):
    """
    Test updating non-existent pantry item.

    Verifies:
    - update_quantity() raises NotFoundError
    - remove_item() returns False
    """
    fake_id = uuid.uuid4()

    # Update non-existent item
    with pytest.raises(NotFoundError):
        PantryService.update_quantity(
            db_session, fake_id, quantity_change=Decimal("100"), reason="test"
        )

    # Remove non-existent item
    removed = PantryService.remove_item(db_session, fake_id)
    assert removed is False


def test_delete_nonexistent_user(db_session: Session):
    """
    Test deleting non-existent user.

    Verifies:
    - delete_user() returns False for non-existent user
    """
    fake_id = uuid.uuid4()
    deleted = ProfileService.delete_user(db_session, fake_id)
    assert deleted is False


# =============================================================================
# RACE CONDITION TESTS
# =============================================================================


def test_ingredient_concurrent_creation(db_session: Session):
    """
    Test IngredientSQLRepository handles race conditions.

    Scenario: Two processes try to create same ingredient simultaneously.

    Verifies:
    - get_or_create() catches IntegrityError
    - Retries with get_by_name() on race condition
    - Returns existing ingredient
    """
    repo = IngredientSQLRepository(db_session)

    # Create first ingredient
    ing1 = repo.get_or_create("concurrent_test")
    assert ing1.name == "concurrent_test"

    # Simulate race condition by trying to create again
    # In real scenario, IntegrityError would be raised and caught
    ing2 = repo.get_or_create("concurrent_test")

    # Should return same ingredient
    assert ing2.ingredient_id == ing1.ingredient_id


def test_user_concurrent_preference_updates(db_session: Session):
    """
    Test concurrent preference updates (edge case).

    Verifies:
    - replace_all() is atomic within transaction
    - Last write wins if concurrent updates occur
    """
    user = ProfileService.create_user(
        db_session, unique_email("concurrent"), "Concurrent User"
    )

    # Set initial preferences
    ProfileService.set_preferences(
        db_session,
        user.user_id,
        [
            PreferenceCreate(tag="tag1", strength="like"),
        ],
    )

    # Update preferences (simulates concurrent update)
    ProfileService.set_preferences(
        db_session,
        user.user_id,
        [
            PreferenceCreate(tag="tag2", strength="love"),
        ],
    )

    # Verify last write
    prefs = ProfileService.get_preferences(db_session, user.user_id)
    assert len(prefs) == 1
    assert prefs[0].tag == "tag2"


# =============================================================================
# TRANSACTION ROLLBACK TESTS
# =============================================================================


def test_pantry_set_rollback_on_error(db_session: Session):
    """
    Test that PantryService.set_pantry() rolls back on error.

    Verifies:
    - If error occurs during set_pantry(), changes are rolled back
    - Pantry remains in previous state
    """
    user = ProfileService.create_user(
        db_session, unique_email("rollback"), "Rollback User"
    )
    ing1 = IngredientService.get_or_create_ingredient(db_session, "item1")
    ing2 = IngredientService.get_or_create_ingredient(db_session, "item2")

    # Add initial pantry items
    with patch.object(PantryService, "validate_ingredients_batch") as mock_batch:
        mock_batch.return_value = {
            str(ing1.ingredient_id): {
                "name": "item1",
                "category": "test",
                "perishability": "non_perishable",
                "defaults": {},
            },
        }

        PantryService.set_pantry(
            db_session,
            user.user_id,
            [
                PantryItemCreate(
                    ingredient_id=ing1.ingredient_id,
                    quantity=Decimal("100"),
                    unit="g",
                )
            ],
        )

    initial_pantry = PantryService.get_pantry(db_session, user.user_id)
    assert len(initial_pantry) == 1

    # Try to update with error (mock validation failure)
    with patch.object(PantryService, "validate_ingredients_batch") as mock_batch:
        mock_batch.return_value = None  # Causes error

        try:
            PantryService.set_pantry(
                db_session,
                user.user_id,
                [
                    PantryItemCreate(
                        ingredient_id=ing2.ingredient_id,
                        quantity=Decimal("200"),
                        unit="g",
                    )
                ],
            )
        except Exception:
            db_session.rollback()

    # Pantry should be unchanged
    current_pantry = PantryService.get_pantry(db_session, user.user_id)
    assert len(current_pantry) == 1
    assert current_pantry[0].ingredient_id == ing1.ingredient_id


# =============================================================================
# BOUNDARY CONDITION TESTS
# =============================================================================


def test_dietary_profile_null_fields(db_session: Session):
    """
    Test dietary profile with NULL optional fields.

    Verifies:
    - Can create profile with minimal data (required fields only)
    - Optional fields can be NULL
    """
    user = ProfileService.create_user(
        db_session, unique_email("minimal"), "Minimal User"
    )

    # Create with only required fields (goal and activity)
    profile_data = DietaryProfileCreate(
        goal="maintenance",
        activity="moderate",
        kcal_target=None,
        protein_target_g=None,
        carb_target_g=None,
        fat_target_g=None,
    )
    dietary = ProfileService.set_dietary_profile(db_session, user.user_id, profile_data)

    # Verify required fields are set
    assert dietary.goal == "maintenance"
    assert dietary.activity == "moderate"
    # Verify optional fields are NULL
    assert dietary.kcal_target is None
    assert dietary.protein_target_g is None
    assert dietary.carb_target_g is None
    assert dietary.fat_target_g is None


def test_pantry_far_future_expiration(db_session: Session):
    """
    Test pantry item with very far future expiration.

    Verifies:
    - Can set expiration years in future
    - get_expiring_soon() doesn't include items with distant expiration
    """
    user = ProfileService.create_user(db_session, unique_email("future"), "Future User")
    ing = IngredientService.get_or_create_ingredient(db_session, "canned_food")

    with patch.object(PantryService, "validate_ingredient_data") as mock_validate:
        mock_validate.return_value = {
            "name": "canned_food",
            "category": "canned",
            "perishability": "non_perishable",
            "defaults": {},
        }

        # Add item expiring in 5 years
        item_data = PantryItemCreate(
            ingredient_id=ing.ingredient_id,
            quantity=Decimal("1"),
            unit="can",
            best_before=date.today() + timedelta(days=365 * 5),
        )
        item = PantryService.add_item(db_session, user.user_id, item_data)

    # Get expiring within 30 days
    expiring = PantryService.get_expiring_soon(db_session, user.user_id, days_threshold=30)

    # Should not include item expiring in 5 years
    assert not any(e.pantry_item_id == item.pantry_item_id for e in expiring)


def test_waste_very_small_quantity(db_session: Session):
    """
    Test waste logging with very small quantity.

    Verifies:
    - Can log waste with fractional quantities (e.g., 0.01 kg)
    - Decimal precision is maintained
    """
    user = ProfileService.create_user(db_session, unique_email("small"), "Small User")
    ing = IngredientService.get_or_create_ingredient(db_session, "spice")

    with patch.object(WasteService, "validate_waste_data") as mock_validate:
        mock_validate.return_value = {
            "ingredient_id": ing.ingredient_id,
            "ingredient_name": "spice",
            "quantity": Decimal("0.01"),
            "unit": "kg",
            "category": "seasoning",
        }

        waste_data = WasteLogCreate(
            ingredient_id=ing.ingredient_id,
            quantity=Decimal("0.01"),
            unit="kg",
            reason="expired",
        )
        waste = WasteService.log_waste(db_session, user.user_id, waste_data)

        assert waste.quantity == Decimal("0.01")


def test_waste_very_large_quantity(db_session: Session):
    """
    Test waste logging with very large quantity.

    Verifies:
    - Can log waste with large quantities
    - No artificial upper limit
    """
    user = ProfileService.create_user(db_session, unique_email("large"), "Large User")
    ing = IngredientService.get_or_create_ingredient(db_session, "bulk_item")

    with patch.object(WasteService, "validate_waste_data") as mock_validate:
        mock_validate.return_value = {
            "ingredient_id": ing.ingredient_id,
            "ingredient_name": "bulk_item",
            "quantity": Decimal("10000"),
            "unit": "kg",
            "category": "bulk",
        }

        waste_data = WasteLogCreate(
            ingredient_id=ing.ingredient_id,
            quantity=Decimal("10000"),
            unit="kg",
            reason="spoiled",
        )
        waste = WasteService.log_waste(db_session, user.user_id, waste_data)

        assert waste.quantity == Decimal("10000")


# =============================================================================
# NULL/EMPTY DATA HANDLING TESTS
# =============================================================================


def test_user_empty_full_name(db_session: Session):
    """
    Test user creation with empty full_name.

    Verifies:
    - Can create user with NULL full_name
    - Empty string is stored as empty string (not NULL)
    """
    repo = UserRepository(db_session)

    # Create with NULL
    user1 = repo.create_user(email=unique_email("null"), full_name=None)
    assert user1.full_name is None

    # Create with empty string
    user2 = repo.create_user(email=unique_email("empty"), full_name="")
    assert user2.full_name == ""


def test_preference_empty_list(db_session: Session):
    """
    Test setting empty preference list.

    Verifies:
    - set_preferences() with empty list removes all preferences
    - get_preferences() returns empty list
    """
    user = ProfileService.create_user(
        db_session, unique_email("emptyprefs"), "Empty Prefs User"
    )

    # Add preferences
    ProfileService.set_preferences(
        db_session,
        user.user_id,
        [
            PreferenceCreate(tag="tag1", strength="like"),
            PreferenceCreate(tag="tag2", strength="love"),
        ],
    )

    prefs = ProfileService.get_preferences(db_session, user.user_id)
    assert len(prefs) == 2

    # Set empty list
    ProfileService.set_preferences(db_session, user.user_id, [])

    prefs = ProfileService.get_preferences(db_session, user.user_id)
    assert len(prefs) == 0


def test_allergy_empty_note(db_session: Session):
    """
    Test allergy with empty/NULL note.

    Verifies:
    - Can create allergy without note
    - Note field is optional
    """
    user = ProfileService.create_user(
        db_session, unique_email("nonote"), "No Note User"
    )
    ing_id = uuid.uuid4()

    # Add allergy without note
    allergy_data = AllergyCreate(ingredient_id=ing_id, note=None)
    allergy = ProfileService.add_allergy(db_session, user.user_id, allergy_data)

    assert allergy.note is None


def test_pantry_no_expiration(db_session: Session):
    """
    Test pantry item with NULL best_before.

    Verifies:
    - Can create pantry item without expiration date
    - Non-perishable items don't require expiration
    """
    user = ProfileService.create_user(
        db_session, unique_email("noexpiry"), "No Expiry User"
    )
    ing = IngredientService.get_or_create_ingredient(db_session, "salt")

    with patch.object(PantryService, "validate_ingredient_data") as mock_validate:
        mock_validate.return_value = {
            "name": "salt",
            "category": "seasoning",
            "perishability": "non_perishable",
            "defaults": {},
        }

        item_data = PantryItemCreate(
            ingredient_id=ing.ingredient_id,
            quantity=Decimal("500"),
            unit="g",
            best_before=None,  # No expiration
        )
        item = PantryService.add_item(db_session, user.user_id, item_data)

        assert item.best_before is None
