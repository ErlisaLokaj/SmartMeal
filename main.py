"""
SmartMeal FastAPI Application
Main entry point with improved architecture, middleware, and configuration management
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import uvicorn
from contextlib import asynccontextmanager
import anyio
import inspect
from typing import Optional

# Import routes from new structure
from api.routes import users, profiles, pantry, waste, health, recipes, recommendations, shopping

# Import database and adapters
from domain.models import init_database
from adapters import graph_adapter, mongo_adapter

# Import configuration
from app.config import settings, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, MONGO_URI, MONGO_DB

# Import middleware
from api.middleware import (
    RequestLoggingMiddleware,
    validation_exception_handler,
    http_exception_handler,
    service_validation_exception_handler,
    not_found_exception_handler,
    general_exception_handler,
)
from app.exceptions import ServiceValidationError, NotFoundError

# Setup logging with configured level and format
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()), format=settings.log_format
)
_logger = logging.getLogger("smartmeal.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for application startup and shutdown.
    Handles database initialization and Neo4j connection with retries.
    """
    is_coro_fn = inspect.iscoroutinefunction(init_database)
    last_exc: Optional[Exception] = None

    # Startup: Initialize database
    _logger.info(f"Starting SmartMeal in {settings.environment.value} mode")

    for attempt in range(1, settings.db_init_attempts + 1):
        try:
            if is_coro_fn:
                await init_database()
            else:
                # Run blocking init in a thread to avoid blocking the event loop
                await anyio.to_thread.run_sync(init_database)

            _logger.info("Database initialization succeeded")
            break
        except Exception as exc:
            last_exc = exc
            _logger.warning(
                "Database init attempt %d/%d failed: %s",
                attempt,
                settings.db_init_attempts,
                exc,
            )
            if attempt < settings.db_init_attempts:
                await anyio.sleep(settings.db_init_delay_sec)
            else:
                _logger.error(
                    "Database initialization failed after %d attempts", attempt
                )
                raise

    # Initialize Neo4j connection (best-effort)
    try:
        graph_adapter.connect(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        _logger.info("Neo4j connection established")
    except Exception as e:
        _logger.warning(
            "Failed to initialize Neo4j adapter; continuing with stub/fallback: %s", e
        )

    # Initialize MongoDB connection (best-effort)
    try:
        mongo_adapter.connect(MONGO_URI, MONGO_DB)
        _logger.info("MongoDB connection established")
    except Exception as e:
        _logger.warning(
            "Failed to initialize MongoDB adapter; continuing without recipes: %s", e
        )

    try:
        yield
    finally:
        # Shutdown: Close connections
        _logger.info("Shutting down SmartMeal")
        try:
            graph_adapter.close()
            _logger.info("Neo4j connection closed")
        except Exception as e:
            _logger.exception("Error closing Neo4j adapter during shutdown: %s", e)
        
        try:
            mongo_adapter.close()
            _logger.info("MongoDB connection closed")
        except Exception as e:
            _logger.exception("Error closing MongoDB adapter during shutdown: %s", e)


# Create FastAPI application with enhanced configuration
app = FastAPI(
    title=settings.api_title,
    version=settings.app_version,
    description=settings.api_description,
    lifespan=lifespan,
    debug=settings.debug,
    openapi_url=(
        f"{settings.api_prefix}/openapi.json" if not settings.is_production() else None
    ),
    docs_url=f"{settings.api_prefix}/docs" if not settings.is_production() else None,
    redoc_url=f"{settings.api_prefix}/redoc" if not settings.is_production() else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Register exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(ServiceValidationError, service_validation_exception_handler)
app.add_exception_handler(NotFoundError, not_found_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include routers from new modular structure
app.include_router(users.router, prefix=settings.api_prefix)
app.include_router(profiles.router, prefix=settings.api_prefix)
app.include_router(pantry.router, prefix=settings.api_prefix)
app.include_router(waste.router, prefix=settings.api_prefix)
app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(recipes.router, prefix=settings.api_prefix)
app.include_router(recommendations.router, prefix=settings.api_prefix)
app.include_router(shopping.router, prefix=settings.api_prefix)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development(),
        log_level=settings.log_level.lower(),
    )
