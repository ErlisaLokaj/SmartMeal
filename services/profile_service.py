from typing import List, Optional, Tuple
from sqlalchemy import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import json
import logging

from domain.models import (
    AppUser,
    DietaryProfile,
    UserAllergy,
    UserPreference,
)
from domain.schemas.profile_schemas import (
    ProfileUpdateRequest,
    DietaryProfileCreate,
    AllergyCreate,
    PreferenceCreate,
)
from repositories import (
    UserRepository,
    DietaryProfileRepository,
    AllergyRepository,
    PreferenceRepository,
)
from app.exceptions import ServiceValidationError, NotFoundError

logger = logging.getLogger("smartmeal.profile")


class ProfileService:
    """Business logic for profile management"""

    @staticmethod
    def get_user_profile(db: Session, user_id: UUID) -> Optional[AppUser]:
        """Retrieve complete user profile with all related data"""
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(user_id)

        if user:
            logger.info(f"profile_fetched user_id={user_id}")
        else:
            logger.warning(f"profile_not_found user_id={user_id}")

        return user

    @staticmethod
    def get_all_users(db: Session) -> List[AppUser]:
        """Return all users (no pagination)."""
        user_repo = UserRepository(db)
        return user_repo.get_all()

    @staticmethod
    def upsert_profile(
        db: Session, user_id: UUID, profile_data: ProfileUpdateRequest
    ) -> Tuple[AppUser, bool]:
        """
        Update or create user profile with dietary settings, allergies, and preferences.
        Implements the complete flow from the sequence diagram.
        Returns a tuple of (AppUser, created_flag).
        """
        created = False
        try:
            # Initialize repositories
            user_repo = UserRepository(db)

            # 1. Get user
            user = user_repo.get_by_id(user_id)

            # If the user doesn't exist, create only if email provided
            if not user:
                if profile_data.email:
                    user = AppUser(
                        user_id=user_id,
                        email=profile_data.email,
                        full_name=profile_data.full_name,
                    )
                    db.add(user)
                    # flush so relationships can reference the user
                    db.flush()
                    created = True
                else:
                    raise ServiceValidationError(
                        "User not found. To create a new user via PUT include 'email' in the payload or use POST /users."
                    )

            # 2. Update basic user info
            if profile_data.full_name is not None:
                user.full_name = profile_data.full_name

            # 3. Upsert dietary profile
            if profile_data.dietary_profile:
                ProfileService._upsert_dietary_profile(
                    db, user_id, profile_data.dietary_profile
                )

            # 4. Upsert allergies (diff-based)
            if profile_data.allergies is not None:
                ProfileService._upsert_allergies(db, user_id, profile_data.allergies)

            # 5. Upsert preferences (diff-based)
            if profile_data.preferences is not None:
                ProfileService._upsert_preferences(
                    db, user_id, profile_data.preferences
                )

            # Commit the transaction
            db.commit()

            # refresh user with latest state
            db.refresh(user)

            logger.info(
                f"profile_upserted user_id={user_id} created={created} "
                f"has_dietary={bool(profile_data.dietary_profile)} "
                f"allergies_count={len(profile_data.allergies or [])} "
                f"preferences_count={len(profile_data.preferences or [])}"
            )

            # return a tuple (user, created) so caller can decide on response code
            return user, created

        except IntegrityError as e:
            db.rollback()
            logger.error(f"profile_upsert_failed user_id={user_id} error={str(e)}")
            raise ServiceValidationError(
                "Database integrity error during profile update"
            )
        except Exception as e:
            logger.error(f"profile_upsert_error user_id={user_id} error={str(e)}")
            raise

    @staticmethod
    def _upsert_dietary_profile(
        db: Session, user_id: UUID, profile_data: DietaryProfileCreate
    ):
        """Upsert dietary profile"""
        dietary_repo = DietaryProfileRepository(db)

        # Prepare kwargs from profile_data
        kwargs = profile_data.model_dump(exclude_unset=True)

        # Convert cuisine lists to JSON strings for storage
        if "cuisine_likes" in kwargs:
            kwargs["cuisine_likes"] = json.dumps(kwargs["cuisine_likes"])
        if "cuisine_dislikes" in kwargs:
            kwargs["cuisine_dislikes"] = json.dumps(kwargs["cuisine_dislikes"])

        # Use repository upsert (only flushes, doesn't commit)
        dietary_repo.upsert(user_id, **kwargs)

    @staticmethod
    def _upsert_allergies(db: Session, user_id: UUID, allergies: List[AllergyCreate]):
        """Diff-based update for allergies: insert new, delete removed, update notes."""
        allergy_repo = AllergyRepository(db)
        allergy_dicts = [
            {"ingredient_id": a.ingredient_id, "note": a.note} for a in allergies
        ]
        allergy_repo.replace_all(user_id, allergy_dicts)

    @staticmethod
    def _upsert_preferences(
        db: Session, user_id: UUID, preferences: List[PreferenceCreate]
    ):
        """Diff-based update for preferences: insert new, delete removed, update strength."""
        pref_repo = PreferenceRepository(db)
        pref_dicts = [{"tag": p.tag, "strength": p.strength} for p in preferences]
        pref_repo.replace_all(user_id, pref_dicts)

    @staticmethod
    def create_user(
        db: Session, email: str, full_name: Optional[str] = None
    ) -> AppUser:
        """Create new user"""
        user_repo = UserRepository(db)
        user = user_repo.create_user(email, full_name)
        logger.info(f"user_created user_id={user.user_id} email={email}")
        return user

    @staticmethod
    def get_dietary_profile(db: Session, user_id: UUID):
        """Return the DietaryProfile for a user or None."""
        dietary_repo = DietaryProfileRepository(db)
        return dietary_repo.get_by_user_id(user_id)

    @staticmethod
    def set_dietary_profile(
        db: Session, user_id: UUID, profile_data: DietaryProfileCreate
    ):
        """Set or replace a user's dietary profile."""
        user_repo = UserRepository(db)
        dietary_repo = DietaryProfileRepository(db)

        user = user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        ProfileService._upsert_dietary_profile(db, user_id, profile_data)
        db.commit()
        return dietary_repo.get_by_user_id(user_id)

    @staticmethod
    def get_preferences(db: Session, user_id: UUID):
        """Return list of UserPreference for a user."""
        pref_repo = PreferenceRepository(db)
        return pref_repo.get_by_user_id(user_id)

    @staticmethod
    def set_preferences(
        db: Session, user_id: UUID, preferences: List[PreferenceCreate]
    ):
        """Replace all preferences for a user."""
        user_repo = UserRepository(db)
        pref_repo = PreferenceRepository(db)

        user = user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        ProfileService._upsert_preferences(db, user_id, preferences)
        db.commit()
        return pref_repo.get_by_user_id(user_id)

    @staticmethod
    def get_allergies(db: Session, user_id: UUID):
        """Return list of UserAllergy for a user."""
        allergy_repo = AllergyRepository(db)
        return allergy_repo.get_by_user_id(user_id)

    @staticmethod
    def set_allergies(db: Session, user_id: UUID, allergies: List[AllergyCreate]):
        """Replace all allergies for a user."""
        user_repo = UserRepository(db)
        allergy_repo = AllergyRepository(db)

        user = user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        ProfileService._upsert_allergies(db, user_id, allergies)
        db.commit()
        return allergy_repo.get_by_user_id(user_id)

    @staticmethod
    def add_preference(db: Session, user_id: UUID, preference: PreferenceCreate):
        """Add a single preference for a user (no dedupe)."""
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        pref_repo = PreferenceRepository(db)
        pref = UserPreference(
            user_id=user_id, tag=preference.tag, strength=preference.strength
        )
        try:
            return pref_repo.create(pref)
        except IntegrityError:
            db.rollback()
            raise ServiceValidationError(
                f"Preference {preference.tag} already exists for user {user_id}"
            )

    @staticmethod
    def remove_preference(db: Session, user_id: UUID, tag: str) -> bool:
        """Remove a single preference by tag. Returns True if deleted."""
        pref_repo = PreferenceRepository(db)
        res = pref_repo.delete_by_user_and_tag(user_id, tag)
        return res > 0

    @staticmethod
    def add_allergy(db: Session, user_id: UUID, allergy: AllergyCreate):
        """Add a single allergy for a user."""
        user_repo = UserRepository(db)
        user = user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        allergy_repo = AllergyRepository(db)
        a = UserAllergy(
            user_id=user_id, ingredient_id=allergy.ingredient_id, note=allergy.note
        )
        try:
            return allergy_repo.create(a)
        except IntegrityError:
            db.rollback()
            raise ServiceValidationError(
                f"Allergy {allergy.ingredient_id} already exists for user {user_id}"
            )

    @staticmethod
    def remove_allergy(db: Session, user_id: UUID, ingredient_id: UUID) -> bool:
        """Remove a single allergy by ingredient_id. Returns True if deleted."""
        allergy_repo = AllergyRepository(db)
        res = allergy_repo.delete_by_user_and_ingredient(user_id, ingredient_id)
        return res > 0

    @staticmethod
    def delete_user(db: Session, user_id: UUID) -> bool:
        """Delete a user and all cascading relations. Returns True if deleted."""
        user_repo = UserRepository(db)
        if user_repo.delete(user_id):
            logger.info(f"user_deleted user_id={user_id}")
            return True
        return False
