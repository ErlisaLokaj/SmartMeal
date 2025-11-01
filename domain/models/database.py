"""
Database configuration and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from core.config import settings

# Create SQLAlchemy Base
Base = declarative_base()

# Create engine
engine = create_engine(settings.postgres_db_url, echo=settings.db_echo, future=True)

# Create session factory
SessionLocal = sessionmaker(bind=engine, future=True)


def init_database():
    """Initialize database schema"""
    # Ensure required Postgres extensions exist (CITEXT used for case-insensitive email)
    with engine.begin() as conn:
        # CREATE EXTENSION requires a superuser
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS citext;")
        Base.metadata.create_all(bind=conn)


def get_db_session():
    """Get database session (for FastAPI dependency injection)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
