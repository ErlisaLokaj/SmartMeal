"""
Shared test fixtures and utilities for SmartMeal test suite.

This module contains common mock objects, helper functions, and test client setup
that are reused across multiple test files to ensure consistency and reduce duplication.
"""

import uuid
from types import SimpleNamespace
from datetime import datetime, date, timedelta
import sqlalchemy
from decimal import Decimal


# Helper function to generate unique emails
def unique_email(prefix: str = "test") -> str:
    """Generate unique email address using UUID to avoid conflicts"""
    return f"{prefix}-{uuid.uuid4()}@example.com"


# Realistic default user profiles
REALISTIC_USERS = {
    "default": {"full_name": "Sarah Martinez", "email_prefix": "sarah.martinez"},
    "athlete": {"full_name": "Michael Chen", "email_prefix": "michael.chen"},
    "casual": {"full_name": "Emma Johnson", "email_prefix": "emma.johnson"},
    "health": {"full_name": "Raj Patel", "email_prefix": "raj.patel"},
}


# Prevent SQLAlchemy from importing DBAPI (psycopg2) during module import.
_real_create_engine = getattr(sqlalchemy, "create_engine", None)


def _dummy_create_engine(*args, **kwargs):
    """
    Simple dummy engine object; init_database is disabled below so it won't be used.
    This prevents actual database connections during testing.
    """
    return SimpleNamespace(begin=lambda *a, **k: None)


sqlalchemy.create_engine = _dummy_create_engine

# Import models and disable their init_database so TestClient startup is safe.
import domain.models as db_models

db_models.init_database = lambda: None

# Restore original create_engine in case other imports need it
if _real_create_engine is not None:
    sqlalchemy.create_engine = _real_create_engine

from fastapi.testclient import TestClient
from main import app

# Create TestClient after we've disabled DB init
client = TestClient(app)


def make_user(user_id=None, email=None, full_name=None, profile_type="default"):
    """
    Create a mock user object for testing with realistic data.

    Args:
        user_id: Optional UUID for the user. Generates new UUID if not provided.
        email: User's email address. Auto-generates if not provided.
        full_name: User's full name. Uses realistic default if not provided.
        profile_type: Type of user profile (default, athlete, casual, health).

    Returns:
        SimpleNamespace: Mock user object with standard user attributes.

    Example:
        >>> user = make_user()  # Sarah Martinez with auto-generated email
        >>> user.email
        'sarah.martinez-<uuid>@example.com'
        >>> athlete = make_user(profile_type="athlete")  # Michael Chen
        >>> athlete.full_name
        'Michael Chen'
    """
    # Use realistic profile defaults
    profile = REALISTIC_USERS.get(profile_type, REALISTIC_USERS["default"])

    uid = user_id or uuid.uuid4()
    now = datetime.utcnow()

    # Generate realistic email if not provided
    if email is None:
        email = unique_email(profile["email_prefix"])

    # Use realistic name if not provided
    if full_name is None:
        full_name = profile["full_name"]

    # SimpleNamespace to mimic ORM with attributes accessed in routes
    user = SimpleNamespace(
        user_id=uid,
        email=email,
        full_name=full_name,
        created_at=now,
        updated_at=now,
        dietary_profile=None,
        allergies=[],
        preferences=[],
    )
    return user


def make_pantry_item(
    pantry_item_id=None,
    user_id=None,
    ingredient_id=None,
    ingredient_name="rice",
    quantity=Decimal("500"),  # 500g - realistic portion
    unit="g",
    best_before=None,
):
    """
    Create a mock pantry item object for testing with realistic quantities.

    Args:
        pantry_item_id: Optional UUID for the pantry item.
        user_id: Optional UUID for the user who owns this item.
        ingredient_id: Optional UUID for the ingredient.
        ingredient_name: Name of ingredient. Defaults to "rice".
        quantity: Amount of the ingredient. Defaults to 500g (realistic portion).
        unit: Unit of measurement. Defaults to "g" (grams).
        best_before: Expiration date. Defaults to 7 days from now.

    Returns:
        SimpleNamespace: Mock pantry item with realistic food quantities.

    Example:
        >>> item = make_pantry_item()  # 500g rice, expires in 7 days
        >>> item.quantity
        Decimal('500')
        >>> chicken = make_pantry_item(
        ...     ingredient_name="chicken breast",
        ...     quantity=Decimal("800"),
        ...     best_before=date.today() + timedelta(days=2)
        ... )
    """
    # Default expiration: 7 days from now (realistic for many foods)
    if best_before is None:
        best_before = date.today() + timedelta(days=7)

    return SimpleNamespace(
        pantry_item_id=pantry_item_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        ingredient_id=ingredient_id or uuid.uuid4(),
        ingredient_name=ingredient_name,
        quantity=quantity,
        unit=unit,
        best_before=best_before,
        source="grocery_store",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def make_waste_log(
    waste_id=None,
    user_id=None,
    ingredient_id=None,
    ingredient_name="tomato",
    quantity=Decimal("150"),  # 150g - realistic waste amount
    unit="g",
    reason="expired",
):
    """
    Create a mock waste log object for testing with realistic waste amounts.

    Args:
        waste_id: Optional UUID for the waste log entry.
        user_id: Optional UUID for the user who logged the waste.
        ingredient_id: Optional UUID for the wasted ingredient.
        ingredient_name: Name of ingredient. Defaults to "tomato".
        quantity: Amount wasted. Defaults to 150g (realistic portion).
        unit: Unit of measurement. Defaults to "g" (grams).
        reason: Reason for waste. Defaults to "expired".
            Valid: expired, spoiled, overcooked, burnt, leftover,
                   freezer_burn, mold, taste_bad, other

    Returns:
        SimpleNamespace: Mock waste log with realistic waste data.

    Example:
        >>> log = make_waste_log()  # 150g tomato, expired
        >>> log.quantity
        Decimal('150')
        >>> log.reason
        'expired'
        >>> moldy = make_waste_log(
        ...     ingredient_name="bread",
        ...     quantity=Decimal("300"),
        ...     reason="mold"
        ... )
    """
    return SimpleNamespace(
        waste_id=waste_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        ingredient_id=ingredient_id or uuid.uuid4(),
        ingredient_name=ingredient_name,
        quantity=Decimal(str(quantity)),
        unit=unit,
        reason=reason,
        occurred_at=datetime.utcnow(),
    )


# =============================================================================
# DATABASE SESSION FIXTURE FOR INTEGRATION TESTS
# =============================================================================

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.config import settings
from typing import Generator


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Create a database session for integration tests.

    This fixture provides a real database session for tests that need
    to verify actual database operations. Each test gets a fresh session
    that is rolled back after the test completes to avoid test pollution.

    Yields:
        Session: SQLAlchemy database session

    Note:
        Tests using this fixture require a running PostgreSQL database.
        The database should be configured via environment variables.
    """
    engine = create_engine(settings.postgres_db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create session
    session = SessionLocal()

    try:
        yield session
    finally:
        # Rollback any changes made during the test
        session.rollback()
        session.close()
