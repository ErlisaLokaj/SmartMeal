"""Repository for CookingLog data access"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from domain.models import CookingLog
from repositories.base import BaseRepository


class CookingLogRepository(BaseRepository[CookingLog]):
    """Repository for cooking log data access"""

    def __init__(self, db: Session):
        super().__init__(db, CookingLog)

    def get_recent_logs(self, user_id: UUID, days: int = 7) -> List[CookingLog]:
        """Get cooking logs for a user within the specified number of days"""
        threshold = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(CookingLog)
            .filter(
                CookingLog.user_id == user_id,
                CookingLog.cooked_at >= threshold,
            )
            .all()
        )

    def get_by_recipe(self, recipe_id: UUID) -> List[CookingLog]:
        """Get all cooking logs for a specific recipe"""
        return self.db.query(CookingLog).filter(CookingLog.recipe_id == recipe_id).all()

    def get_by_user_and_recipe(
        self, user_id: UUID, recipe_id: UUID
    ) -> List[CookingLog]:
        """Get cooking logs for a specific user and recipe"""
        return (
            self.db.query(CookingLog)
            .filter(
                CookingLog.user_id == user_id,
                CookingLog.recipe_id == recipe_id,
            )
            .all()
        )
