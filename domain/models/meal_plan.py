"""
Meal planning and recipe-related models.
"""

from sqlalchemy import Column, Text, TIMESTAMP, ForeignKey, Numeric, Date, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from domain.models.database import Base


class MealPlan(Base):
    """Weekly meal plans"""

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
    """Individual meals in a meal plan"""

    __tablename__ = "meal_entry"

    meal_entry_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(
        UUID(as_uuid=True), ForeignKey("meal_plan.plan_id", ondelete="CASCADE")
    )
    day = Column(Date)
    slot = Column(Text)  # breakfast, lunch, dinner, snack
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
    """Snapshot of recipe at time of meal planning"""

    __tablename__ = "meal_entry_recipe_snapshot"

    meal_entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meal_entry.meal_entry_id", ondelete="CASCADE"),
        primary_key=True,
    )
    base_recipe_id = Column(UUID(as_uuid=True))
    ingredients = Column(Text)  # JSON stored as text
    steps = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    meal_entry = relationship("MealEntry", back_populates="recipe_snapshot")


class ShoppingList(Base):
    """Shopping lists generated from meal plans"""

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
    """Individual items in a shopping list"""

    __tablename__ = "shopping_list_item"

    list_item_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    list_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shopping_list.list_id", ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_id = Column(UUID(as_uuid=True), nullable=False)
    needed_qty = Column(Numeric)
    unit = Column(Text)
    checked = Column(Boolean, default=False)
    from_recipe_id = Column(UUID(as_uuid=True), nullable=True)
    note = Column(Text)

    list = relationship("ShoppingList", back_populates="items")


class CookingLog(Base):
    """Log of cooked recipes"""

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
