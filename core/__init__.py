"""
Core package - Application configuration and utilities.
Contains settings, exceptions, and core business logic.
"""

from core.config import settings
from core.exceptions import (
    ServiceValidationError,
    NotFoundError,
    ConflictError,
    UnauthorizedError,
)

__all__ = [
    "settings",
    "ServiceValidationError",
    "NotFoundError",
    "ConflictError",
    "UnauthorizedError",
]
