from sqlalchemy import Column, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from domain.models.database import Base
from domain.enums import PreferenceStrength

class UserPreference(Base):
    __tablename__ = "user_preference"

    preference_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("app_user.user_id", ondelete="CASCADE"), nullable=False)
    tag = Column(Text, nullable=False)
    strength = Column(Enum(PreferenceStrength, name="preferencestrength", create_type=False), nullable=False)
