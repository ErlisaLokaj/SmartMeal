"""
Meal Plan Repository - Data access layer for meal plan operations
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from repositories.base import BaseRepository
from domain.models import MealPlan, MealEntry


class MealPlanRepository(BaseRepository[MealPlan]):
    """Repository for meal plan data access"""

    def __init__(self, db: Session):
        super().__init__(db, MealPlan)

    def get_by_id(self, plan_id: UUID) -> Optional[MealPlan]:
        """Get meal plan by ID"""
        return self.db.query(MealPlan).filter(MealPlan.plan_id == plan_id).first()

    def get_by_id_and_user(self, plan_id: UUID, user_id: UUID) -> Optional[MealPlan]:
        """Get meal plan by ID for specific user"""
        return (
            self.db.query(MealPlan)
            .filter(MealPlan.plan_id == plan_id, MealPlan.user_id == user_id)
            .first()
        )


class MealEntryRepository(BaseRepository[MealEntry]):
    """Repository for meal entry data access"""

    def __init__(self, db: Session):
        super().__init__(db, MealEntry)

    def get_by_id(self, entry_id: UUID) -> Optional[MealEntry]:
        """Get meal entry by ID"""
        return self.db.query(MealEntry).filter(MealEntry.entry_id == entry_id).first()

    def get_by_plan_id(self, plan_id: UUID) -> List[MealEntry]:
        """Get all meal entries for a plan"""
        return self.db.query(MealEntry).filter(MealEntry.plan_id == plan_id).all()
