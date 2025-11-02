"""
Shared test fixtures and utilities for SmartMeal test suite.

This module contains common mock objects, helper functions, and test client setup
that are reused across multiple test files to ensure consistency and reduce duplication.
"""

import uuid
from types import SimpleNamespace
from datetime import datetime
import sqlalchemy
from decimal import Decimal


# Helper function to generate unique emails
def unique_email(prefix: str = "test") -> str:
    """Generate unique email address using UUID to avoid conflicts"""
    return f"{prefix}-{uuid.uuid4()}@example.com"


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


def make_user(user_id=None, email=unique_email("test"), full_name="Test User"):
    """
    Create a mock user object for testing.

    Args:
        user_id: Optional UUID for the user. Generates new UUID if not provided.
        email: User's email address. Defaults to "test@example.com".
        full_name: User's full name. Defaults to "Test User".

    Returns:
        SimpleNamespace: Mock user object with standard user attributes.

    Example:
        >>> user = make_user()
        >>> user.email
        'test@example.com'
        >>> custom_user = make_user(email=unique_email("custom"))
    """
    uid = user_id or uuid.uuid4()
    now = datetime.utcnow()
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
    quantity=1.0,
    unit="pcs",
    best_before=None,
):
    """
    Create a mock pantry item object for testing.

    Args:
        pantry_item_id: Optional UUID for the pantry item.
        user_id: Optional UUID for the user who owns this item.
        ingredient_id: Optional UUID for the ingredient.
        quantity: Amount of the ingredient. Defaults to 1.0.
        unit: Unit of measurement. Defaults to "pcs".
        best_before: Expiry date. Defaults to None.

    Returns:
        SimpleNamespace: Mock pantry item with standard attributes.

    Example:
        >>> item = make_pantry_item(quantity=2.5, unit="kg")
        >>> item.quantity
        2.5
        >>> item.unit
        'kg'
    """
    return SimpleNamespace(
        pantry_item_id=pantry_item_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        ingredient_id=ingredient_id or uuid.uuid4(),
        quantity=quantity,
        unit=unit,
        best_before=best_before,
        source=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def make_waste_log(
    waste_id=None,
    user_id=None,
    ingredient_id=None,
    quantity=2.5,
    unit="kg",
    reason="expired",
):
    """
    Create a mock waste log object for testing.

    Args:
        waste_id: Optional UUID for the waste log entry.
        user_id: Optional UUID for the user who logged the waste.
        ingredient_id: Optional UUID for the wasted ingredient.
        quantity: Amount wasted. Defaults to 2.5.
        unit: Unit of measurement. Defaults to "kg".
        reason: Reason for waste. Defaults to "expired".

    Returns:
        SimpleNamespace: Mock waste log with standard attributes.

    Example:
        >>> log = make_waste_log(quantity=1.0, reason="spoiled")
        >>> log.quantity
        Decimal('1.0')
        >>> log.reason
        'spoiled'
    """
    return SimpleNamespace(
        waste_id=waste_id or uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        ingredient_id=ingredient_id or uuid.uuid4(),
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
from core.config import settings
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

