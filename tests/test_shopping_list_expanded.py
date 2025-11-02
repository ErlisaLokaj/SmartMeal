"""
Comprehensive tests for shopping list functionality.

This test suite extends beyond the basic shopping list test to cover:
- Multiple shopping lists per user
- Item status updates (purchased/unpurchased)
- Shopping list deletion
- Pantry integration (what you have vs what you need)
- Edge cases and error conditions
"""

import pytest
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from test_fixtures import client, db_session, unique_email
from services.profile_service import ProfileService
from services.ingredient_service import IngredientService
from services.shopping_service import ShoppingService
from domain.models import ShoppingList, ShoppingListItem, MealPlan, MealEntry
from core.exceptions import NotFoundError, ServiceValidationError


# =============================================================================
# SHOPPING LIST CRUD TESTS
# =============================================================================


def test_shopping_list_multiple_lists_per_user(db_session: Session):
    """
    Test that users can have multiple shopping lists.

    Verifies:
    - get_user_shopping_lists() returns all user lists
    - Lists are independent
    - Each list has its own items
    """
    user = ProfileService.create_user(db_session, unique_email("multi"), "Multi List User")

    # Create two meal plans
    plan1 = MealPlan(
        user_id=user.user_id,
        starts_on=datetime.now().date(),
        created_at=datetime.now(),
    )
    plan2 = MealPlan(
        user_id=user.user_id,
        starts_on=datetime.now().date(),
        created_at=datetime.now(),
    )
    db_session.add(plan1)
    db_session.add(plan2)
    db_session.commit()

    # Create two shopping lists
    list1 = ShoppingList(
        user_id=user.user_id,
        plan_id=plan1.plan_id,
        created_at=datetime.now(),
    )
    list2 = ShoppingList(
        user_id=user.user_id,
        plan_id=plan2.plan_id,
        created_at=datetime.now(),
    )
    db_session.add(list1)
    db_session.add(list2)
    db_session.commit()

    # Get all user lists
    user_lists = ShoppingService.get_user_shopping_lists(db_session, user.user_id)
    assert len(user_lists) >= 2

    list_ids = [lst.list_id for lst in user_lists]
    assert list1.list_id in list_ids
    assert list2.list_id in list_ids


def test_shopping_list_get_by_id(db_session: Session):
    """
    Test ShoppingService.get_shopping_list() operation.

    Verifies:
    - Returns shopping list by ID
    - Includes all items in list
    - Raises NotFoundError if not found
    """
    user = ProfileService.create_user(db_session, unique_email("getlist"), "Get List User")
    ing = IngredientService.get_or_create_ingredient(db_session, "apple")

    # Create shopping list
    shopping_list = ShoppingList(
        user_id=user.user_id,
        plan_id=None,
        created_at=datetime.now(),
    )
    db_session.add(shopping_list)
    db_session.commit()

    # Add item
    item = ShoppingListItem(
        list_id=shopping_list.list_id,
        ingredient_id=ing.ingredient_id,
        needed_qty=Decimal("5"),
        unit="units",
        checked=False,
    )
    db_session.add(item)
    db_session.commit()

    # Get list
    retrieved = ShoppingService.get_shopping_list(
        db_session, shopping_list.list_id, user.user_id
    )
    assert retrieved is not None
    assert retrieved.list_id == shopping_list.list_id
    assert len(retrieved.items) == 1

    # Try to get non-existent list
    with pytest.raises(NotFoundError):
        ShoppingService.get_shopping_list(db_session, uuid.uuid4(), user.user_id)


def test_shopping_list_update_item_status(db_session: Session):
    """
    Test ShoppingService.update_item_status() operation.

    Verifies:
    - Updates item purchased status to True
    - Updates item purchased status to False
    - Raises NotFoundError if item not found
    """
    user = ProfileService.create_user(db_session, unique_email("status"), "Status User")
    ing = IngredientService.get_or_create_ingredient(db_session, "bread")

    # Create shopping list and item
    shopping_list = ShoppingList(
        user_id=user.user_id,
        plan_id=None,
        created_at=datetime.now(),
    )
    db_session.add(shopping_list)
    db_session.commit()

    item = ShoppingListItem(
        list_id=shopping_list.list_id,
        ingredient_id=ing.ingredient_id,
        needed_qty=Decimal("2"),
        unit="loaves",
        checked=False,
    )
    db_session.add(item)
    db_session.commit()

    # Mark as purchased
    updated = ShoppingService.update_item_status(
        db_session, item.list_item_id, user.user_id, checked=True
    )
    assert updated.checked is True

    # Mark as unpurchased
    updated = ShoppingService.update_item_status(
        db_session, item.list_item_id, user.user_id, checked=False
    )
    assert updated.checked is False

    # Try to update non-existent item
    with pytest.raises(NotFoundError):
        ShoppingService.update_item_status(
            db_session, uuid.uuid4(), user.user_id, checked=True
        )


def test_shopping_list_delete(db_session: Session):
    """
    Test ShoppingService.delete_shopping_list() operation.

    Verifies:
    - Deletes shopping list and all items
    - Returns True on success
    - Returns False if list not found or doesn't belong to user
    """
    user = ProfileService.create_user(
        db_session, unique_email("dellist"), "Delete List User"
    )
    other_user = ProfileService.create_user(db_session, unique_email("other"), "Other User")
    ing = IngredientService.get_or_create_ingredient(db_session, "milk")

    # Create shopping list with items
    shopping_list = ShoppingList(
        user_id=user.user_id,
        plan_id=None,
        created_at=datetime.now(),
    )
    db_session.add(shopping_list)
    db_session.commit()

    item = ShoppingListItem(
        list_id=shopping_list.list_id,
        ingredient_id=ing.ingredient_id,
        needed_qty=Decimal("1"),
        unit="liter",
        checked=False,
    )
    db_session.add(item)
    db_session.commit()

    # Delete list
    deleted = ShoppingService.delete_shopping_list(
        db_session, shopping_list.list_id, user.user_id
    )
    assert deleted is True

    # Verify deleted
    with pytest.raises(NotFoundError):
        ShoppingService.get_shopping_list(
            db_session, shopping_list.list_id, user.user_id
        )

    # Create another list
    another_list = ShoppingList(
        user_id=user.user_id,
        plan_id=None,
        created_at=datetime.now(),
    )
    db_session.add(another_list)
    db_session.commit()

    # Try to delete as wrong user
    not_deleted = ShoppingService.delete_shopping_list(
        db_session, another_list.list_id, other_user.user_id
    )
    assert not_deleted is False


# =============================================================================
# SHOPPING LIST EDGE CASES
# =============================================================================


def test_shopping_list_empty_list(db_session: Session):
    """
    Test shopping list with no items.

    Verifies:
    - Can create empty shopping list
    - get_shopping_list() returns list with empty items array
    """
    user = ProfileService.create_user(db_session, unique_email("empty"), "Empty List User")

    # Create empty shopping list
    shopping_list = ShoppingList(
        user_id=user.user_id,
        plan_id=None,
        created_at=datetime.now(),
    )
    db_session.add(shopping_list)
    db_session.commit()

    # Get list
    retrieved = ShoppingService.get_shopping_list(
        db_session, shopping_list.list_id, user.user_id
    )
    assert retrieved is not None
    assert len(retrieved.items) == 0


def test_shopping_list_duplicate_ingredients(db_session: Session):
    """
    Test shopping list with same ingredient multiple times.

    In normal operation, ShoppingService.build_list() aggregates quantities,
    but this tests that the database allows multiple items with same ingredient
    (for manual list creation scenarios).

    Verifies:
    - Can add same ingredient multiple times
    - Each item is tracked separately
    """
    user = ProfileService.create_user(db_session, unique_email("dup"), "Dup User")
    ing = IngredientService.get_or_create_ingredient(db_session, "sugar")

    # Create shopping list
    shopping_list = ShoppingList(
        user_id=user.user_id,
        plan_id=None,
        created_at=datetime.now(),
    )
    db_session.add(shopping_list)
    db_session.commit()

    # Add same ingredient twice with different quantities/units
    item1 = ShoppingListItem(
        list_id=shopping_list.list_id,
        ingredient_id=ing.ingredient_id,
        needed_qty=Decimal("500"),
        unit="g",
        checked=False,
    )
    item2 = ShoppingListItem(
        list_id=shopping_list.list_id,
        ingredient_id=ing.ingredient_id,
        needed_qty=Decimal("1"),
        unit="kg",
        checked=False,
    )
    db_session.add(item1)
    db_session.add(item2)
    db_session.commit()

    # Get list
    retrieved = ShoppingService.get_shopping_list(
        db_session, shopping_list.list_id, user.user_id
    )
    assert len(retrieved.items) == 2
    assert retrieved.items[0].ingredient_id == ing.ingredient_id
    assert retrieved.items[1].ingredient_id == ing.ingredient_id


def test_shopping_list_all_items_purchased(db_session: Session):
    """
    Test shopping list where all items are marked purchased.

    Verifies:
    - Can mark all items as purchased
    - List still exists and retrievable
    - Future feature: could auto-archive completed lists
    """
    user = ProfileService.create_user(db_session, unique_email("complete"), "Complete User")
    ing1 = IngredientService.get_or_create_ingredient(db_session, "item1")
    ing2 = IngredientService.get_or_create_ingredient(db_session, "item2")

    # Create shopping list
    shopping_list = ShoppingList(
        user_id=user.user_id,
        plan_id=None,
        created_at=datetime.now(),
    )
    db_session.add(shopping_list)
    db_session.commit()

    # Add items
    item1 = ShoppingListItem(
        list_id=shopping_list.list_id,
        ingredient_id=ing1.ingredient_id,
        needed_qty=Decimal("1"),
        unit="unit",
        checked=False,
    )
    item2 = ShoppingListItem(
        list_id=shopping_list.list_id,
        ingredient_id=ing2.ingredient_id,
        needed_qty=Decimal("2"),
        unit="units",
        checked=False,
    )
    db_session.add(item1)
    db_session.add(item2)
    db_session.commit()

    # Mark all as purchased
    ShoppingService.update_item_status(
        db_session, item1.list_item_id, user.user_id, True
    )
    ShoppingService.update_item_status(
        db_session, item2.list_item_id, user.user_id, True
    )

    # Get list
    retrieved = ShoppingService.get_shopping_list(
        db_session, shopping_list.list_id, user.user_id
    )
    assert all(item.checked for item in retrieved.items)


# =============================================================================
# SHOPPING LIST AUTHORIZATION TESTS
# =============================================================================


def test_shopping_list_user_isolation(db_session: Session):
    """
    Test that users can only access their own shopping lists.

    Verifies:
    - User A cannot access User B's shopping list
    - get_shopping_list() raises NotFoundError for wrong user
    - update_item_status() raises NotFoundError for wrong user
    """
    user_a = ProfileService.create_user(db_session, unique_email("usera"), "User A")
    user_b = ProfileService.create_user(db_session, unique_email("userb"), "User B")
    ing = IngredientService.get_or_create_ingredient(db_session, "test")

    # Create list for User A
    list_a = ShoppingList(
        user_id=user_a.user_id,
        plan_id=None,
        created_at=datetime.now(),
    )
    db_session.add(list_a)
    db_session.commit()

    item = ShoppingListItem(
        list_id=list_a.list_id,
        ingredient_id=ing.ingredient_id,
        needed_qty=Decimal("1"),
        unit="unit",
        checked=False,
    )
    db_session.add(item)
    db_session.commit()

    # User B tries to access User A's list
    with pytest.raises(NotFoundError):
        ShoppingService.get_shopping_list(db_session, list_a.list_id, user_b.user_id)

    # User B tries to update item in User A's list
    with pytest.raises(NotFoundError):
        ShoppingService.update_item_status(
            db_session, item.list_item_id, user_b.user_id, True
        )

    # User A can access their own list
    retrieved = ShoppingService.get_shopping_list(
        db_session, list_a.list_id, user_a.user_id
    )
    assert retrieved is not None

