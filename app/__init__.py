"""
App package - Application configuration and core utilities.
Contains settings, exceptions, and foundational application code.
"""

from app.config import settings
from app.exceptions import (
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
