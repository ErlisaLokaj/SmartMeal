"""Repository for CookingLog data access"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID
from decimal import Decimal

from sqlalchemy.orm import Session

from domain.models import CookingLog
from repositories.base import BaseRepository


class CookingLogRepository(BaseRepository[CookingLog]):
    """Repository for cooking log data access"""

    def __init__(self, db: Session):
        super().__init__(db, CookingLog)

    def create_cooking_log(
        self, user_id: UUID, recipe_id: str, servings: int
    ) -> CookingLog:
        """
        Create a new cooking log entry.

        Args:
            user_id: User's UUID
            recipe_id: Recipe ID (string from MongoDB)
            servings: Number of servings cooked

        Returns:
            Created CookingLog instance
        """
        cooking_log = CookingLog(
            user_id=user_id,
            recipe_id=recipe_id,
            servings=Decimal(str(servings)),
        )
        self.db.add(cooking_log)
        self.db.commit()
        self.db.refresh(cooking_log)
        return cooking_log

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
