"""
Application configuration with Pydantic Settings for validation and type safety.
Supports environment-specific configurations and .env file loading.
"""

import os
from enum import Enum
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, PostgresDsn, field_validator


class Environment(str, Enum):
    """Application environment types"""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class Settings(BaseSettings):
    """
    Application settings with validation.
    Settings are loaded from environment variables or .env file.
    """

    # Application settings
    app_name: str = Field(default="SmartMeal", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    environment: Environment = Field(
        default=Environment.DEVELOPMENT, description="Application environment"
    )
    debug: bool = Field(default=False, description="Debug mode")

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")

    # Database settings - PostgreSQL
    postgres_db_url: str = Field(
        default="postgresql+psycopg2://user@localhost:5432/smartmeal",
        description="PostgreSQL connection URL",
    )
    db_echo: bool = Field(default=False, description="SQLAlchemy echo SQL statements")
    db_init_attempts: int = Field(
        default=8, ge=1, description="Database initialization retry attempts"
    )
    db_init_delay_sec: float = Field(
        default=2.0, ge=0, description="Delay between DB init attempts"
    )

    # Neo4j settings
    neo4j_uri: str = Field(
        default="bolt://localhost:7687", description="Neo4j connection URI"
    )
    neo4j_user: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: str = Field(default="password", description="Neo4j password")

    # MongoDB settings
    mongo_uri: str = Field(
        default="mongodb://localhost:27017", description="MongoDB connection URI"
    )
    mongo_db_name: str = Field(default="smartmeal", description="MongoDB database name")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="%(asctime)s %(levelname)s %(name)s: %(message)s",
        description="Log format string",
    )

    # CORS settings
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(
        default=True, description="Allow CORS credentials"
    )
    cors_allow_methods: list[str] = Field(
        default=["*"], description="Allowed HTTP methods"
    )
    cors_allow_headers: list[str] = Field(
        default=["*"], description="Allowed HTTP headers"
    )

    # API settings
    api_prefix: str = Field(default="", description="API route prefix")
    api_title: str = Field(
        default="SmartMeal API", description="API documentation title"
    )
    api_description: str = Field(
        default="Intelligent meal planning system with multi-database support",
        description="API documentation description",
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment(cls, v):
        """Validate and normalize environment value"""
        if isinstance(v, str):
            return Environment(v.lower())
        return v

    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment == Environment.PRODUCTION

    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment == Environment.DEVELOPMENT

    def is_testing(self) -> bool:
        """Check if running in testing environment"""
        return self.environment == Environment.TESTING


# Global settings instance
settings = Settings()

# Legacy support - export individual values for backward compatibility
POSTGRES_DB_URL = settings.postgres_db_url
NEO4J_URI = settings.neo4j_uri
NEO4J_USER = settings.neo4j_user
NEO4J_PASSWORD = settings.neo4j_password
MONGO_URI = settings.mongo_uri
MONGO_DB = settings.mongo_db_name

