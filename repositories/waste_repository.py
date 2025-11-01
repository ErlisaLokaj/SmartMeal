"""
Waste Repository - Data access layer for waste logging operations
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from repositories.base import BaseRepository
from domain.models import WasteLog


class WasteRepository(BaseRepository[WasteLog]):
    """Repository for waste log data access"""

    def __init__(self, db: Session):
        super().__init__(db, WasteLog)

    def get_by_id(self, waste_id: UUID) -> Optional[WasteLog]:
        """Get waste log by ID"""
        return self.db.query(WasteLog).filter(WasteLog.waste_id == waste_id).first()

    def get_by_user_id(
        self, user_id: UUID, start_date: datetime = None, end_date: datetime = None
    ) -> List[WasteLog]:
        """Get all waste logs for a user within a date range"""
        query = self.db.query(WasteLog).filter(WasteLog.user_id == user_id)

        if start_date:
            query = query.filter(WasteLog.occurred_at >= start_date)
        if end_date:
            query = query.filter(WasteLog.occurred_at <= end_date)

        return query.order_by(WasteLog.occurred_at.desc()).all()

    def create_waste_log(
        self,
        user_id: UUID,
        ingredient_id: UUID,
        quantity,
        unit: str,
        reason: str = None,
    ) -> WasteLog:
        """Create a new waste log entry"""
        waste_log = WasteLog(
            user_id=user_id,
            ingredient_id=ingredient_id,
            quantity=quantity,
            unit=unit,
            reason=reason,
        )
        self.db.add(waste_log)
        self.db.commit()
        self.db.refresh(waste_log)
        return waste_log

    def get_total_waste_count(self, user_id: UUID, horizon_days: int) -> int:
        """Get total count of waste logs for a user within horizon"""
        start_date = datetime.utcnow() - timedelta(days=horizon_days)
        return (
            self.db.query(func.count(WasteLog.waste_id))
            .filter(WasteLog.user_id == user_id, WasteLog.occurred_at >= start_date)
            .scalar()
        )

    def get_aggregated_by_ingredient(
        self, user_id: UUID, horizon_days: int, limit: int = 10
    ) -> List[dict]:
        """Get waste aggregated by ingredient"""
        start_date = datetime.utcnow() - timedelta(days=horizon_days)

        results = (
            self.db.query(
                WasteLog.ingredient_id,
                WasteLog.unit,
                func.sum(WasteLog.quantity).label("total_quantity"),
                func.count(WasteLog.waste_id).label("waste_count"),
            )
            .filter(WasteLog.user_id == user_id, WasteLog.occurred_at >= start_date)
            .group_by(WasteLog.ingredient_id, WasteLog.unit)
            .order_by(func.sum(WasteLog.quantity).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "ingredient_id": r.ingredient_id,
                "unit": r.unit,
                "total_quantity": r.total_quantity,
                "waste_count": r.waste_count,
            }
            for r in results
        ]

    def get_aggregated_by_reason(
        self, user_id: UUID, horizon_days: int, limit: int = 5
    ) -> List[dict]:
        """Get waste aggregated by reason"""
        start_date = datetime.utcnow() - timedelta(days=horizon_days)

        results = (
            self.db.query(WasteLog.reason, func.count(WasteLog.waste_id).label("count"))
            .filter(WasteLog.user_id == user_id, WasteLog.occurred_at >= start_date)
            .group_by(WasteLog.reason)
            .order_by(func.count(WasteLog.waste_id).desc())
            .limit(limit)
            .all()
        )

        return [
            {"reason": r.reason or "unspecified", "count": r.count} for r in results
        ]
