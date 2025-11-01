"""
User Repository - Data access layer for user-related operations
"""

from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from core.base import BaseRepository
from core.database.models import AppUser, UserAllergy, UserPreference, DietaryProfile
from core.exceptions import ServiceValidationError


class UserRepository(BaseRepository[AppUser]):
    """Repository for user data access"""

    def __init__(self, db: Session):
        super().__init__(db, AppUser)

    def get_by_id(self, user_id: UUID) -> Optional[AppUser]:
        """Get user by ID with all relationships loaded"""
        return self.db.query(AppUser).filter(AppUser.user_id == user_id).first()

    def get_by_email(self, email: str) -> Optional[AppUser]:
        """Get user by email"""
        return self.db.query(AppUser).filter(AppUser.email == email).first()

    def create_user(self, user_id: UUID, email: str, full_name: str = None) -> AppUser:
        """Create a new user"""
        user = AppUser(user_id=user_id, email=email, full_name=full_name)
        try:
            self.db.add(user)
            self.db.flush()
            return user
        except IntegrityError as e:
            self.db.rollback()
            raise ServiceValidationError(f"User with email {email} already exists")

    def update_user(self, user: AppUser) -> AppUser:
        """Update user information"""
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user_id: UUID) -> bool:
        """Delete user and all related data (cascade)"""
        user = self.get_by_id(user_id)
        if user:
            self.db.delete(user)
            self.db.commit()
            return True
        return False


class DietaryProfileRepository(BaseRepository[DietaryProfile]):
    """Repository for dietary profile data access"""

    def __init__(self, db: Session):
        super().__init__(db, DietaryProfile)

    def get_by_user_id(self, user_id: UUID) -> Optional[DietaryProfile]:
        """Get dietary profile for a user"""
        return (
            self.db.query(DietaryProfile)
            .filter(DietaryProfile.user_id == user_id)
            .first()
        )

    def upsert(self, user_id: UUID, **kwargs) -> DietaryProfile:
        """Create or update dietary profile"""
        profile = self.get_by_user_id(user_id)
        if profile:
            for key, value in kwargs.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
        else:
            profile = DietaryProfile(user_id=user_id, **kwargs)
            self.db.add(profile)
        self.db.flush()
        return profile


class AllergyRepository(BaseRepository[UserAllergy]):
    """Repository for allergy data access"""

    def __init__(self, db: Session):
        super().__init__(db, UserAllergy)

    def get_by_user_id(self, user_id: UUID) -> List[UserAllergy]:
        """Get all allergies for a user"""
        return self.db.query(UserAllergy).filter(UserAllergy.user_id == user_id).all()

    def delete_by_user_id(self, user_id: UUID) -> int:
        """Delete all allergies for a user"""
        count = (
            self.db.query(UserAllergy).filter(UserAllergy.user_id == user_id).delete()
        )
        self.db.flush()
        return count

    def bulk_create(self, user_id: UUID, allergies: List[dict]) -> List[UserAllergy]:
        """Create multiple allergies for a user"""
        allergy_objs = [
            UserAllergy(user_id=user_id, **allergy) for allergy in allergies
        ]
        self.db.bulk_save_objects(allergy_objs, return_defaults=True)
        self.db.flush()
        return allergy_objs


class PreferenceRepository(BaseRepository[UserPreference]):
    """Repository for preference data access"""

    def __init__(self, db: Session):
        super().__init__(db, UserPreference)

    def get_by_user_id(self, user_id: UUID) -> List[UserPreference]:
        """Get all preferences for a user"""
        return (
            self.db.query(UserPreference)
            .filter(UserPreference.user_id == user_id)
            .all()
        )

    def delete_by_user_id(self, user_id: UUID) -> int:
        """Delete all preferences for a user"""
        count = (
            self.db.query(UserPreference)
            .filter(UserPreference.user_id == user_id)
            .delete()
        )
        self.db.flush()
        return count

    def bulk_create(
        self, user_id: UUID, preferences: List[dict]
    ) -> List[UserPreference]:
        """Create multiple preferences for a user"""
        pref_objs = [UserPreference(user_id=user_id, **pref) for pref in preferences]
        self.db.bulk_save_objects(pref_objs, return_defaults=True)
        self.db.flush()
        return pref_objs
