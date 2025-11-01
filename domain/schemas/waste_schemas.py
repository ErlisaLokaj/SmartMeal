from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class WasteLogCreate(BaseModel):
    """Schema for creating a new waste log entry"""

    ingredient_id: UUID
    quantity: Decimal = Field(..., gt=0, description="Quantity of wasted ingredient")
    unit: Optional[str] = Field(
        None, description="Unit of measurement (e.g., 'g', 'kg', 'ml', 'pieces')"
    )
    reason: Optional[str] = Field(
        None, description="Reason for waste (e.g., 'expired', 'spoiled', 'excess')"
    )
    pantry_item_id: Optional[UUID] = Field(
        None,
        description="Optional: Pantry item ID to auto-remove/decrement when logging waste",
    )
    auto_remove_from_pantry: bool = Field(
        default=False,
        description="If true and pantry_item_id provided, automatically update pantry",
    )

    model_config = {"from_attributes": True}


class WasteLogResponse(BaseModel):
    """Schema for waste log response"""

    waste_id: UUID
    user_id: UUID
    ingredient_id: UUID
    quantity: Decimal
    unit: Optional[str]
    reason: Optional[str]
    occurred_at: datetime

    model_config = {"from_attributes": True}


class WasteByIngredient(BaseModel):
    """Aggregated waste data by ingredient"""

    ingredient_id: UUID
    ingredient_name: Optional[str] = None
    total_quantity: Decimal
    unit: Optional[str]
    waste_count: int
    percentage_of_total: Optional[float] = None


class WasteByCategory(BaseModel):
    """Aggregated waste data by category"""

    category: str
    total_quantity: Decimal
    waste_count: int
    percentage_of_total: Optional[float] = None


class WasteTrend(BaseModel):
    """Waste trend data over time"""

    period: str  # e.g., "2025-10", "2025-W44" (week), or "2025-10-31" (day)
    total_quantity: Decimal
    waste_count: int


class WasteInsightsResponse(BaseModel):
    """Comprehensive waste insights dashboard data"""

    total_waste_count: int
    total_quantity: Decimal
    most_wasted_ingredients: List[WasteByIngredient]
    waste_by_category: List[WasteByCategory]
    waste_trends: List[WasteTrend]
    common_reasons: List[Dict[str, Any]]  # [{reason: str, count: int}, ...]
    horizon_days: int

    model_config = {"from_attributes": True}
