"""
Pantry and inventory-related models.
"""

from sqlalchemy import (
    Column,
    Text,
    TIMESTAMP,
    ForeignKey,
    Numeric,
    Date,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from domain.models.database import Base


class PantryItem(Base):
    """User pantry items (available ingredients)"""

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
            "user_id",
            "ingredient_id",
            "unit",
            "best_before",
            name="uq_pantry_user_ingredient_unit_expiry",
        ),
        CheckConstraint("quantity >= 0", name="ck_pantry_quantity_nonneg"),
    )


class WasteLog(Base):
    """Food waste tracking"""

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
