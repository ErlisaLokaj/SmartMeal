from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Text,
    Date,
    TIMESTAMP,
    Numeric,
    Boolean,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID, CITEXT
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func
import uuid
import enum
from core.config import POSTGRES_DB_URL
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import Date, Boolean
from sqlalchemy import UniqueConstraint, CheckConstraint

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


class Ingredient(Base):
    """
    Master ingredient table - single source of truth.

    All recipes, pantry items, and allergies reference ingredients by ingredient_id.
    """
    __tablename__ = "ingredient"

    ingredient_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False, unique=True)
    category = Column(Text)
    is_allergen = Column(Boolean, default=False)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint('name', name='uq_ingredient_name'),
    )


# Models
class AppUser(Base):
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


class PantryItem(Base):
    __tablename__ = "pantry_item"

    pantry_item_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_id = Column(UUID(as_uuid=True), nullable=False)
    quantity = Column(Numeric, nullable=False, default=0)
    unit = Column(Text)
    best_before = Column(Date)
    source = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("AppUser", back_populates="pantry_items")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "ingredient_id", "unit", name="uq_pantry_user_ingredient_unit"
        ),
        CheckConstraint("quantity >= 0", name="ck_pantry_quantity_nonneg"),
    )


class MealPlan(Base):
    __tablename__ = "meal_plan"

    plan_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    starts_on = Column(Date)
    ends_on = Column(Date)
    title = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("AppUser", back_populates="meal_plans")
    entries = relationship(
        "MealEntry", back_populates="plan", cascade="all, delete-orphan"
    )


class MealEntry(Base):
    __tablename__ = "meal_entry"

    meal_entry_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(
        UUID(as_uuid=True), ForeignKey("meal_plan.plan_id", ondelete="CASCADE")
    )
    day = Column(Date)
    slot = Column(Text)  # meal_slot enum could be added
    recipe_id = Column(UUID(as_uuid=True))
    servings = Column(Numeric)
    notes = Column(Text)

    plan = relationship("MealPlan", back_populates="entries")
    recipe_snapshot = relationship(
        "MealEntryRecipeSnapshot",
        back_populates="meal_entry",
        uselist=False,
        cascade="all, delete-orphan",
    )


class MealEntryRecipeSnapshot(Base):
    __tablename__ = "meal_entry_recipe_snapshot"

    meal_entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meal_entry.meal_entry_id", ondelete="CASCADE"),
        primary_key=True,
    )
    base_recipe_id = Column(UUID(as_uuid=True))
    ingredients = Column(Text)  # stored as jsonb in PG; using Text for simplicity
    steps = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    meal_entry = relationship("MealEntry", back_populates="recipe_snapshot")


class ShoppingList(Base):
    __tablename__ = "shopping_list"

    list_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id = Column(UUID(as_uuid=True), ForeignKey("meal_plan.plan_id"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    status = Column(Text)

    user = relationship("AppUser", back_populates="shopping_lists")
    items = relationship(
        "ShoppingListItem", back_populates="list", cascade="all, delete-orphan"
    )


class ShoppingListItem(Base):
    __tablename__ = "shopping_list_item"

    list_item_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    list_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shopping_list.list_id", ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_id = Column(UUID(as_uuid=True), nullable=False)
    ingredient_name = Column(Text)
    needed_qty = Column(Numeric)
    unit = Column(Text)
    checked = Column(Boolean, default=False)
    from_recipe_id = Column(UUID(as_uuid=True), nullable=True)
    note = Column(Text)

    list = relationship("ShoppingList", back_populates="items")


class CookingLog(Base):
    __tablename__ = "cooking_log"

    cook_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    recipe_id = Column(UUID(as_uuid=True))
    cooked_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    servings = Column(Numeric)

    user = relationship("AppUser", back_populates="cooking_logs")


class WasteLog(Base):
    __tablename__ = "waste_log"

    waste_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_id = Column(UUID(as_uuid=True))
    quantity = Column(Numeric)
    unit = Column(Text)
    reason = Column(Text)
    occurred_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    user = relationship("AppUser", back_populates="waste_logs")


def init_database():
    """Initialize database schema"""
    # Ensure required Postgres extensions exist (CITEXT used for case-insensitive email)
    # Use a transactional connection so the extension is created before tables are created.
    with engine.begin() as conn:
        # CREATE EXTENSION requires a superuser; the default Postgres docker user is a superuser.
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS citext;")
        Base.metadata.create_all(bind=conn)


def get_db():
    """Get database session (for FastAPI dependency injection)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
