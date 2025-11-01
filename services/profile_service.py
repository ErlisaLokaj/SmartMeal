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
from core.exceptions import ServiceValidationError, NotFoundError

logger = logging.getLogger("smartmeal.profile")


class ProfileService:
    """Business logic for profile management"""

    @staticmethod
    def get_user_profile(db: Session, user_id: UUID) -> Optional[AppUser]:
        """Retrieve complete user profile with all related data"""
        user = db.query(AppUser).filter(AppUser.user_id == user_id).first()

        if user:
            logger.info(f"profile_fetched user_id={user_id}")
        else:
            logger.warning(f"profile_not_found user_id={user_id}")

        return user

    @staticmethod
    def get_all_users(db: Session) -> List[AppUser]:
        """Return all users (no pagination)."""
        return db.query(AppUser).all()

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
            # Use a transactional block so delete/insert operations are atomic
            with db.begin():
                # 1. Get user
                user = db.query(AppUser).filter(AppUser.user_id == user_id).first()

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
                    ProfileService._upsert_allergies(
                        db, user_id, profile_data.allergies
                    )

                # 5. Upsert preferences (diff-based)
                if profile_data.preferences is not None:
                    ProfileService._upsert_preferences(
                        db, user_id, profile_data.preferences
                    )

                # transaction will commit on block exit

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
        dietary = (
            db.query(DietaryProfile).filter(DietaryProfile.user_id == user_id).first()
        )

        if dietary:
            # Update existing
            for key, value in profile_data.model_dump(exclude_unset=True).items():
                if key in ["cuisine_likes", "cuisine_dislikes"]:
                    # dietary model stores cuisine lists as JSON text; keep current schema but normalize here
                    setattr(dietary, key, json.dumps(value))
                else:
                    setattr(dietary, key, value)
        else:
            # Create new
            dietary = DietaryProfile(
                user_id=user_id,
                goal=profile_data.goal,
                activity=profile_data.activity,
                kcal_target=profile_data.kcal_target,
                protein_target_g=profile_data.protein_target_g,
                carb_target_g=profile_data.carb_target_g,
                fat_target_g=profile_data.fat_target_g,
                cuisine_likes=json.dumps(
                    profile_data.model_dump().get("cuisine_likes") or []
                ),
                cuisine_dislikes=json.dumps(
                    profile_data.model_dump().get("cuisine_dislikes") or []
                ),
            )
            db.add(dietary)

    @staticmethod
    def _upsert_allergies(db: Session, user_id: UUID, allergies: List[AllergyCreate]):
        """Diff-based update for allergies: insert new, delete removed, update notes."""
        existing = db.query(UserAllergy).filter(UserAllergy.user_id == user_id).all()
        existing_map = {str(a.ingredient_id): a for a in existing}

        incoming_ids = {str(a.ingredient_id) for a in allergies}

        # delete removed
        for ingr_id, obj in existing_map.items():
            if ingr_id not in incoming_ids:
                db.delete(obj)

        # upsert incoming
        for allergy in allergies:
            key = str(allergy.ingredient_id)
            if key in existing_map:
                obj = existing_map[key]
                obj.note = allergy.note
            else:
                db.add(
                    UserAllergy(
                        user_id=user_id,
                        ingredient_id=allergy.ingredient_id,
                        note=allergy.note,
                    )
                )

    @staticmethod
    def _upsert_preferences(
        db: Session, user_id: UUID, preferences: List[PreferenceCreate]
    ):
        """Diff-based update for preferences: insert new, delete removed, update strength."""
        existing = (
            db.query(UserPreference).filter(UserPreference.user_id == user_id).all()
        )
        existing_map = {p.tag: p for p in existing}

        incoming_tags = {p.tag for p in preferences}

        # delete removed
        for tag, obj in existing_map.items():
            if tag not in incoming_tags:
                db.delete(obj)

        # upsert incoming
        for pref in preferences:
            if pref.tag in existing_map:
                obj = existing_map[pref.tag]
                obj.strength = pref.strength
            else:
                db.add(
                    UserPreference(
                        user_id=user_id, tag=pref.tag, strength=pref.strength
                    )
                )

    @staticmethod
    def create_user(
        db: Session, email: str, full_name: Optional[str] = None
    ) -> AppUser:
        """Create new user"""
        user = AppUser(email=email, full_name=full_name)
        db.add(user)

        try:
            db.commit()
            db.refresh(user)
            logger.info(f"user_created user_id={user.user_id} email={email}")
            return user
        except IntegrityError:
            db.rollback()
            raise ServiceValidationError(f"User with email {email} already exists")

    @staticmethod
    def get_dietary_profile(db: Session, user_id: UUID):
        """Return the DietaryProfile for a user or None."""
        return (
            db.query(DietaryProfile).filter(DietaryProfile.user_id == user_id).first()
        )

    @staticmethod
    def set_dietary_profile(
        db: Session, user_id: UUID, profile_data: DietaryProfileCreate
    ):
        """Set or replace a user's dietary profile."""
        user = db.query(AppUser).filter(AppUser.user_id == user_id).first()
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        ProfileService._upsert_dietary_profile(db, user_id, profile_data)
        db.commit()
        return (
            db.query(DietaryProfile).filter(DietaryProfile.user_id == user_id).first()
        )

    @staticmethod
    def get_preferences(db: Session, user_id: UUID):
        """Return list of UserPreference for a user."""
        return db.query(UserPreference).filter(UserPreference.user_id == user_id).all()

    @staticmethod
    def set_preferences(
        db: Session, user_id: UUID, preferences: List[PreferenceCreate]
    ):
        """Replace all preferences for a user."""
        user = db.query(AppUser).filter(AppUser.user_id == user_id).first()
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        ProfileService._upsert_preferences(db, user_id, preferences)
        db.commit()
        return db.query(UserPreference).filter(UserPreference.user_id == user_id).all()

    @staticmethod
    def get_allergies(db: Session, user_id: UUID):
        """Return list of UserAllergy for a user."""
        return db.query(UserAllergy).filter(UserAllergy.user_id == user_id).all()

    @staticmethod
    def set_allergies(db: Session, user_id: UUID, allergies: List[AllergyCreate]):
        """Replace all allergies for a user."""
        user = db.query(AppUser).filter(AppUser.user_id == user_id).first()
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        ProfileService._upsert_allergies(db, user_id, allergies)
        db.commit()
        return db.query(UserAllergy).filter(UserAllergy.user_id == user_id).all()

    @staticmethod
    def add_preference(db: Session, user_id: UUID, preference: PreferenceCreate):
        """Add a single preference for a user (no dedupe)."""
        user = db.query(AppUser).filter(AppUser.user_id == user_id).first()
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        pref = UserPreference(
            user_id=user_id, tag=preference.tag, strength=preference.strength
        )
        db.add(pref)
        try:
            db.commit()
            db.refresh(pref)
            return pref
        except IntegrityError:
            db.rollback()
            raise ServiceValidationError(
                f"Preference {preference.tag} already exists for user {user_id}"
            )

    @staticmethod
    def remove_preference(db: Session, user_id: UUID, tag: str) -> bool:
        """Remove a single preference by tag. Returns True if deleted."""
        res = (
            db.query(UserPreference)
            .filter(UserPreference.user_id == user_id, UserPreference.tag == tag)
            .delete()
        )
        if res:
            db.commit()
            return True
        return False

    @staticmethod
    def add_allergy(db: Session, user_id: UUID, allergy: AllergyCreate):
        """Add a single allergy for a user."""
        user = db.query(AppUser).filter(AppUser.user_id == user_id).first()
        if not user:
            raise NotFoundError(f"User not found: {user_id}")

        a = UserAllergy(
            user_id=user_id, ingredient_id=allergy.ingredient_id, note=allergy.note
        )
        db.add(a)
        try:
            db.commit()
            db.refresh(a)
            return a
        except IntegrityError:
            db.rollback()
            raise ServiceValidationError(
                f"Allergy {allergy.ingredient_id} already exists for user {user_id}"
            )

    @staticmethod
    def remove_allergy(db: Session, user_id: UUID, ingredient_id: UUID) -> bool:
        """Remove a single allergy by ingredient_id. Returns True if deleted."""
        res = (
            db.query(UserAllergy)
            .filter(
                UserAllergy.user_id == user_id,
                UserAllergy.ingredient_id == ingredient_id,
            )
            .delete()
        )
        if res:
            db.commit()
            return True
        return False

    @staticmethod
    def delete_user(db: Session, user_id: UUID) -> bool:
        """Delete a user and all cascading relations. Returns True if deleted."""
        res = db.query(AppUser).filter(AppUser.user_id == user_id).delete()
        if res:
            db.commit()
            logger.info(f"user_deleted user_id={user_id}")
            return True
        return False
