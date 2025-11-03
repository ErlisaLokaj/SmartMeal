"""
User Repository - Data access layer for user-related operations
"""

from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from repositories.base import BaseRepository
from domain.models import AppUser, UserAllergy, UserPreference, DietaryProfile
from app.exceptions import ServiceValidationError


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

    def create_user(self, email: str, full_name: str = None) -> AppUser:
        """Create a new user"""
        user = AppUser(email=email, full_name=full_name)
        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
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

    def get_ingredient_ids(self, user_id: UUID) -> List[UUID]:
        """Get list of ingredient IDs user is allergic to"""
        allergies = self.get_by_user_id(user_id)
        return [allergy.ingredient_id for allergy in allergies]

    def delete_by_user_id(self, user_id: UUID) -> int:
        """Delete all allergies for a user"""
        count = (
            self.db.query(UserAllergy).filter(UserAllergy.user_id == user_id).delete()
        )
        self.db.flush()
        return count

    def delete_by_user_and_ingredient(self, user_id: UUID, ingredient_id: UUID) -> int:
        """Delete a specific allergy by user_id and ingredient_id"""
        count = (
            self.db.query(UserAllergy)
            .filter(
                UserAllergy.user_id == user_id,
                UserAllergy.ingredient_id == ingredient_id,
            )
            .delete()
        )
        self.db.commit()
        return count

    def create(self, allergy: UserAllergy) -> UserAllergy:
        """Create a single allergy"""
        self.db.add(allergy)
        self.db.commit()
        self.db.refresh(allergy)
        return allergy

    def bulk_create(self, user_id: UUID, allergies: List[dict]) -> List[UserAllergy]:
        """Create multiple allergies for a user"""
        allergy_objs = [
            UserAllergy(user_id=user_id, **allergy) for allergy in allergies
        ]
        self.db.bulk_save_objects(allergy_objs, return_defaults=True)
        self.db.flush()
        return allergy_objs

    def replace_all(self, user_id: UUID, allergies: List[dict]) -> List[UserAllergy]:
        """Replace all allergies for a user (diff-based update).

        - Deletes allergies that are no longer in the list
        - Updates notes for existing allergies
        - Adds new allergies
        """
        existing = self.get_by_user_id(user_id)
        existing_map = {str(a.ingredient_id): a for a in existing}

        incoming_ids = {str(a["ingredient_id"]) for a in allergies}

        # Delete removed allergies
        for ingr_id, obj in existing_map.items():
            if ingr_id not in incoming_ids:
                self.db.delete(obj)

        # Upsert incoming allergies
        for allergy_data in allergies:
            key = str(allergy_data["ingredient_id"])
            if key in existing_map:
                # Update existing
                obj = existing_map[key]
                obj.note = allergy_data.get("note")
            else:
                # Add new
                self.db.add(
                    UserAllergy(
                        user_id=user_id,
                        ingredient_id=allergy_data["ingredient_id"],
                        note=allergy_data.get("note"),
                    )
                )

        self.db.flush()
        return self.get_by_user_id(user_id)


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

    def delete_by_user_and_tag(self, user_id: UUID, tag: str) -> int:
        """Delete a specific preference by user_id and tag"""
        count = (
            self.db.query(UserPreference)
            .filter(UserPreference.user_id == user_id, UserPreference.tag == tag)
            .delete()
        )
        self.db.commit()
        return count

    def create(self, preference: UserPreference) -> UserPreference:
        """Create a single preference"""
        self.db.add(preference)
        self.db.commit()
        self.db.refresh(preference)
        return preference

    def bulk_create(
        self, user_id: UUID, preferences: List[dict]
    ) -> List[UserPreference]:
        """Create multiple preferences for a user"""
        pref_objs = [UserPreference(user_id=user_id, **pref) for pref in preferences]
        self.db.bulk_save_objects(pref_objs, return_defaults=True)
        self.db.flush()
        return pref_objs

    def replace_all(
        self, user_id: UUID, preferences: List[dict]
    ) -> List[UserPreference]:
        """Replace all preferences for a user (diff-based update).

        - Deletes preferences that are no longer in the list
        - Updates strength for existing preferences
        - Adds new preferences
        """
        existing = self.get_by_user_id(user_id)
        existing_map = {p.tag: p for p in existing}

        incoming_tags = {p["tag"] for p in preferences}

        # Delete removed preferences
        for tag, obj in existing_map.items():
            if tag not in incoming_tags:
                self.db.delete(obj)

        # Upsert incoming preferences
        for pref_data in preferences:
            tag = pref_data["tag"]
            if tag in existing_map:
                # Update existing
                obj = existing_map[tag]
                obj.strength = pref_data.get("strength", "neutral")
            else:
                # Add new
                self.db.add(
                    UserPreference(
                        user_id=user_id,
                        tag=tag,
                        strength=pref_data.get("strength", "neutral"),
                    )
                )

        self.db.flush()
        return self.get_by_user_id(user_id)
