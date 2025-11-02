"""
Ingredient model - Master ingredient table.
Single source of truth for all ingredients across the system.
"""

from sqlalchemy import Column, Text, Boolean, TIMESTAMP, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from domain.models.database import Base


class Ingredient(Base):
    """
    Master ingredient table - single source of truth.

    All recipes, pantry items, and allergies reference ingredients by ingredient_id.
    This ensures consistency across MongoDB (recipes) and PostgreSQL (pantry, allergies).
    """

    __tablename__ = "ingredient"

    ingredient_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False, unique=True, index=True)
    category = Column(Text)
    is_allergen = Column(Boolean, default=False)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("name", name="uq_ingredient_name"),)

    def __repr__(self):
        return f"<Ingredient(id={self.ingredient_id}, name='{self.name}')>"
