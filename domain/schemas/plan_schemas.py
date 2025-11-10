from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GeneratePlanRequest(BaseModel):
    user_id: UUID
    week_start: Optional[date] = None
    days: int = Field(default=7, ge=1, le=14)
    use_substitutions: bool = False


class PlanResponse(BaseModel):
    plan_id: UUID
    week_start: date
    days: int
    message: Optional[str] = None


class PlanEntryResponse(BaseModel):
    meal_entry_id: UUID
    recipe_id: str
    day_index: int
    servings: int
