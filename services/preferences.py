import logging
from sqlalchemy.orm import Session
from uuid import UUID
from domain.models.preferences import UserPreference
from domain.enums import PreferenceStrength

logger = logging.getLogger("smartmeal.user_prefs")


class UserPreferenceService:
    """Handles adding and updating user preferences."""

    @staticmethod
    def add_preferences(db: Session, user_id: UUID, preferences: list[dict]):
        """
        Add or update user preferences.

        Args:
            db: SQLAlchemy session
            user_id: User UUID
            preferences: List of {"tag": str, "strength": str}
        """
        for pref in preferences:
            tag = pref.get("tag")
            strength = pref.get("strength")

            if not tag or not strength:
                continue

            try:
                existing = (
                    db.query(UserPreference)
                    .filter(UserPreference.user_id == user_id, UserPreference.tag == tag)
                    .first()
                )

                if existing:
                    existing.strength = PreferenceStrength(strength)
                    logger.info(f"Updated preference: {tag} -> {strength}")
                else:
                    new_pref = UserPreference(
                        user_id=user_id,
                        tag=tag,
                        strength=PreferenceStrength(strength),
                    )
                    db.add(new_pref)
                    logger.info(f"Added preference: {tag} -> {strength}")

            except Exception as e:
                logger.error(f"Failed to process preference {tag}: {e}")

        db.commit()
