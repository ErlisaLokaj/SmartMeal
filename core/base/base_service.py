"""
Base service interface for business logic layer.
Services orchestrate business operations using repositories.
"""

from typing import Generic, TypeVar
from abc import ABC
import logging

RepositoryType = TypeVar("RepositoryType")


class BaseService(Generic[RepositoryType], ABC):
    """
    Base service providing common functionality.
    All service classes should inherit from this class.
    """

    def __init__(self, logger_name: str):
        self.logger = logging.getLogger(logger_name)

    def log_info(self, message: str, **kwargs):
        """Log info message with structured data"""
        extra_data = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        self.logger.info(f"{message} {extra_data}".strip())

    def log_warning(self, message: str, **kwargs):
        """Log warning message with structured data"""
        extra_data = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        self.logger.warning(f"{message} {extra_data}".strip())

    def log_error(self, message: str, **kwargs):
        """Log error message with structured data"""
        extra_data = " ".join([f"{k}={v}" for k, v in kwargs.items()])
        self.logger.error(f"{message} {extra_data}".strip())
