"""
Database configuration and session management.
"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from core.config import settings

logger = logging.getLogger("smartmeal.database")

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
        try:
            # CREATE EXTENSION requires a superuser or appropriate privileges
            conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS citext;")
            logger.info("PostgreSQL extension 'citext' ensured")
        except Exception as e:
            # Log warning but don't fail - citext is nice-to-have for case-insensitive emails
            # The app will still work without it
            logger.warning(
                f"Could not create citext extension (requires superuser privileges): {e}"
            )
            logger.info(
                "Database will work without citext extension (emails will be case-sensitive)"
            )

        Base.metadata.create_all(bind=conn)
        logger.info("Database tables created successfully")


def get_db_session():
    """Get database session (for FastAPI dependency injection)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
