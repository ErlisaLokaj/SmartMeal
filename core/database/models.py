from sqlalchemy import (
    create_engine, Column, String, Integer, Text, Date, 
    TIMESTAMP, Numeric, Boolean, ForeignKey, CheckConstraint,
    UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, CITEXT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func
import uuid
import enum

Base = declarative_base()
engine = create_engine(POSTGRES_DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, future=True)


# Enums
class GoalType(str, enum.Enum):
    WEIGHT_LOSS = "weight_loss"
    MUSCLE_GAIN = "muscle_gain"
    MAINTENANCE = "maintenance"
    HEALTH = "health"


class ActivityLevel(str, enum.Enum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


class PreferenceStrength(str, enum.Enum):
    AVOID = "avoid"
    NEUTRAL = "neutral"
    LIKE = "like"
    LOVE = "love"


# Models
class AppUser(Base):
    __tablename__ = "app_user"
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(CITEXT, unique=True, nullable=False)
    full_name = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    dietary_profile = relationship("DietaryProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    allergies = relationship("UserAllergy", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")


class DietaryProfile(Base):
    __tablename__ = "dietary_profile"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("app_user.user_id", ondelete="CASCADE"), primary_key=True)
    goal = Column(SQLEnum(GoalType), nullable=False, default=GoalType.MAINTENANCE)
    activity = Column(SQLEnum(ActivityLevel), nullable=False, default=ActivityLevel.MODERATE)
    kcal_target = Column(Integer)
    protein_target_g = Column(Numeric(6, 2))
    carb_target_g = Column(Numeric(6, 2))
    fat_target_g = Column(Numeric(6, 2))
    cuisine_likes = Column(Text)  # JSON array stored as text
    cuisine_dislikes = Column(Text)  # JSON array stored as text
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("AppUser", back_populates="dietary_profile")


class UserAllergy(Base):
    __tablename__ = "user_allergy"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("app_user.user_id", ondelete="CASCADE"), primary_key=True)
    ingredient_id = Column(UUID(as_uuid=True), primary_key=True)  # References Neo4j
    note = Column(Text)
    
    # Relationships
    user = relationship("AppUser", back_populates="allergies")


class UserPreference(Base):
    __tablename__ = "user_preference"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("app_user.user_id", ondelete="CASCADE"), primary_key=True)
    tag = Column(Text, primary_key=True)
    strength = Column(SQLEnum(PreferenceStrength), nullable=False, default=PreferenceStrength.NEUTRAL)
    
    # Relationships
    user = relationship("AppUser", back_populates="preferences")


def init_database():
    """Initialize database schema"""
    Base.metadata.create_all(engine)


def get_db():
    """Get database session (for FastAPI dependency injection)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
