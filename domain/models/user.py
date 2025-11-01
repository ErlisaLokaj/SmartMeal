"""
User-related database models.
"""

from sqlalchemy import (
    Column,
    Text,
    TIMESTAMP,
    ForeignKey,
    UUID as SQLUUID,
    Enum as SQLEnum,
    Integer,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID, CITEXT
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from domain.models.database import Base
from domain.enums import GoalType, ActivityLevel, PreferenceStrength


class AppUser(Base):
    """User account model"""

    __tablename__ = "app_user"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(CITEXT, unique=True, nullable=False)
    full_name = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    dietary_profile = relationship(
        "DietaryProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    allergies = relationship(
        "UserAllergy", back_populates="user", cascade="all, delete-orphan"
    )
    preferences = relationship(
        "UserPreference", back_populates="user", cascade="all, delete-orphan"
    )
    pantry_items = relationship(
        "PantryItem", back_populates="user", cascade="all, delete-orphan"
    )
    meal_plans = relationship(
        "MealPlan", back_populates="user", cascade="all, delete-orphan"
    )
    shopping_lists = relationship(
        "ShoppingList", back_populates="user", cascade="all, delete-orphan"
    )
    cooking_logs = relationship(
        "CookingLog", back_populates="user", cascade="all, delete-orphan"
    )
    waste_logs = relationship(
        "WasteLog", back_populates="user", cascade="all, delete-orphan"
    )


class DietaryProfile(Base):
    """User dietary profile and nutritional goals"""

    __tablename__ = "dietary_profile"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    goal = Column(SQLEnum(GoalType), nullable=False, default=GoalType.MAINTENANCE)
    activity = Column(
        SQLEnum(ActivityLevel), nullable=False, default=ActivityLevel.MODERATE
    )
    kcal_target = Column(Integer)
    protein_target_g = Column(Numeric(6, 2))
    carb_target_g = Column(Numeric(6, 2))
    fat_target_g = Column(Numeric(6, 2))
    cuisine_likes = Column(Text)  # JSON array stored as text
    cuisine_dislikes = Column(Text)  # JSON array stored as text
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("AppUser", back_populates="dietary_profile")


class UserAllergy(Base):
    """User allergies to ingredients"""

    __tablename__ = "user_allergy"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    ingredient_id = Column(UUID(as_uuid=True), primary_key=True)  # References Neo4j
    note = Column(Text)

    # Relationships
    user = relationship("AppUser", back_populates="allergies")


class UserPreference(Base):
    """User food preferences and likes/dislikes"""

    __tablename__ = "user_preference"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag = Column(Text, primary_key=True)
    strength = Column(
        SQLEnum(PreferenceStrength), nullable=False, default=PreferenceStrength.NEUTRAL
    )

    # Relationships
    user = relationship("AppUser", back_populates="preferences")
