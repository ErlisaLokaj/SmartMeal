from typing import List, Optional
from sqlalchemy import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import json
import logging

from core.database.models import *
from core.schemas.profile_schemas import *

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
    def upsert_profile(
        db: Session, 
        user_id: UUID, 
        profile_data: ProfileUpdateRequest
    ) -> AppUser:
        """
        Update or create user profile with dietary settings, allergies, and preferences.
        Implements the complete flow from the sequence diagram.
        """
        try:
            # 1. Get or create user
            user = db.query(AppUser).filter(AppUser.user_id == user_id).first()
            
            if not user:
                raise ValueError(f"User not found: {user_id}")
            
            # 2. Update basic user info
            if profile_data.full_name is not None:
                user.full_name = profile_data.full_name
            
            # 3. Upsert dietary profile
            if profile_data.dietary_profile:
                ProfileService._upsert_dietary_profile(db, user_id, profile_data.dietary_profile)
            
            # 4. Upsert allergies
            if profile_data.allergies is not None:
                ProfileService._upsert_allergies(db, user_id, profile_data.allergies)
            
            # 5. Upsert preferences
            if profile_data.preferences is not None:
                ProfileService._upsert_preferences(db, user_id, profile_data.preferences)
            
            db.commit()
            db.refresh(user)
            
            logger.info(
                f"profile_upserted user_id={user_id} "
                f"has_dietary={bool(profile_data.dietary_profile)} "
                f"allergies_count={len(profile_data.allergies or [])} "
                f"preferences_count={len(profile_data.preferences or [])}"
            )
            
            return user
            
        except IntegrityError as e:
            db.rollback()
            logger.error(f"profile_upsert_failed user_id={user_id} error={str(e)}")
            raise ValueError("Database integrity error during profile update")
        except Exception as e:
            db.rollback()
            logger.error(f"profile_upsert_error user_id={user_id} error={str(e)}")
            raise
    
    @staticmethod
    def _upsert_dietary_profile(
        db: Session, 
        user_id: UUID, 
        profile_data: DietaryProfileCreate
    ):
        """Upsert dietary profile"""
        dietary = db.query(DietaryProfile).filter(
            DietaryProfile.user_id == user_id
        ).first()
        
        if dietary:
            # Update existing
            for key, value in profile_data.dict(exclude_unset=True).items():
                if key in ["cuisine_likes", "cuisine_dislikes"]:
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
                cuisine_likes=json.dumps(profile_data.cuisine_likes),
                cuisine_dislikes=json.dumps(profile_data.cuisine_dislikes)
            )
            db.add(dietary)
    
    @staticmethod
    def _upsert_allergies(
        db: Session, 
        user_id: UUID, 
        allergies: List[AllergyCreate]
    ):
        """Replace all allergies for user"""
        # Delete existing
        db.query(UserAllergy).filter(UserAllergy.user_id == user_id).delete()
        
        # Insert new
        for allergy in allergies:
            db.add(UserAllergy(
                user_id=user_id,
                ingredient_id=allergy.ingredient_id,
                note=allergy.note
            ))
    
    @staticmethod
    def _upsert_preferences(
        db: Session, 
        user_id: UUID, 
        preferences: List[PreferenceCreate]
    ):
        """Replace all preferences for user"""
        # Delete existing
        db.query(UserPreference).filter(UserPreference.user_id == user_id).delete()
        
        # Insert new
        for pref in preferences:
            db.add(UserPreference(
                user_id=user_id,
                tag=pref.tag,
                strength=pref.strength
            ))
    
    @staticmethod
    def create_user(db: Session, email: str, full_name: Optional[str] = None) -> AppUser:
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
            raise ValueError(f"User with email {email} already exists")