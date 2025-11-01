"""
Standardized API response models and utilities.
Provides consistent response formatting across all endpoints.
"""

from typing import Generic, TypeVar, Optional, Any, List
from pydantic import BaseModel, Field
from datetime import datetime

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Generic API response wrapper"""

    success: bool = Field(..., description="Indicates if the operation was successful")
    message: Optional[str] = Field(None, description="Human-readable message")
    data: Optional[T] = Field(None, description="Response payload")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated API response"""

    items: List[T] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")

    model_config = {"from_attributes": True}


class ErrorDetail(BaseModel):
    """Detailed error information"""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    field: Optional[str] = Field(None, description="Field that caused the error")
    details: Optional[dict] = Field(None, description="Additional error details")


class ErrorResponse(BaseModel):
    """Standardized error response"""

    success: bool = Field(False, description="Always false for errors")
    error: ErrorDetail = Field(..., description="Error details")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Error timestamp"
    )


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: Optional[str] = Field(None, description="Service version")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Check timestamp"
    )


def success_response(
    data: Any = None, message: str = None, status_code: int = 200
) -> dict:
    """Create a standardized success response"""
    return {
        "success": True,
        "message": message,
        "data": data,
        "timestamp": datetime.utcnow(),
    }


def error_response(
    code: str,
    message: str,
    field: str = None,
    details: dict = None,
    status_code: int = 400,
) -> dict:
    """Create a standardized error response"""
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "field": field,
            "details": details,
        },
        "timestamp": datetime.utcnow(),
    }


def paginated_response(
    items: List[Any],
    total: int,
    page: int,
    page_size: int,
) -> dict:
    """Create a standardized paginated response"""
    total_pages = (total + page_size - 1) // page_size
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }
