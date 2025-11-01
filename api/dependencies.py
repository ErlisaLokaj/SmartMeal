"""
API dependencies for dependency injection
"""

from typing import Generator
from sqlalchemy.orm import Session
from domain.models import get_db_session


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency for FastAPI routes.

    Usage:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            # Use db session here
            pass
    """
    yield from get_db_session()
