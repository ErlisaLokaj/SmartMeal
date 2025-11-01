"""
Centralized dependency injection for FastAPI.
This module provides all injectable dependencies used across the application.
"""

from typing import Generator
from sqlalchemy.orm import Session

from core.database.models import SessionLocal
from core.repositories import (
    UserRepository,
    WasteRepository,
    PantryRepository,
    DietaryProfileRepository,
    AllergyRepository,
    PreferenceRepository,
)


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency.
    Yields a SQLAlchemy session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_repository(db: Session = None) -> UserRepository:
    """Get user repository instance"""
    if db is None:
        db = next(get_db())
    return UserRepository(db)


def get_waste_repository(db: Session = None) -> WasteRepository:
    """Get waste repository instance"""
    if db is None:
        db = next(get_db())
    return WasteRepository(db)


def get_pantry_repository(db: Session = None) -> PantryRepository:
    """Get pantry repository instance"""
    if db is None:
        db = next(get_db())
    return PantryRepository(db)


def get_dietary_profile_repository(db: Session = None) -> DietaryProfileRepository:
    """Get dietary profile repository instance"""
    if db is None:
        db = next(get_db())
    return DietaryProfileRepository(db)


def get_allergy_repository(db: Session = None) -> AllergyRepository:
    """Get allergy repository instance"""
    if db is None:
        db = next(get_db())
    return AllergyRepository(db)


def get_preference_repository(db: Session = None) -> PreferenceRepository:
    """Get preference repository instance"""
    if db is None:
        db = next(get_db())
    return PreferenceRepository(db)
