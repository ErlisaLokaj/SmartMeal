from fastapi import FastAPI
import logging
import uvicorn
from api.routes import router
from core.database.models import init_database
from adapters import graph_adapter
from core.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from contextlib import asynccontextmanager
import anyio
import inspect
from typing import Optional
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
_logger = logging.getLogger("smartmeal.main")

# Configuration for DB init retries (helpful when DB container takes time to start)
MAX_DB_INIT_ATTEMPTS = int(os.getenv("DB_INIT_ATTEMPTS", "8"))
DB_INIT_DELAY_SEC = float(os.getenv("DB_INIT_DELAY_SEC", "2.0"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context that initializes the DB on startup.

    It detects whether `init_database` is async or sync and runs it appropriately.
    Retries a few times with delay to tolerate DB startup lag in Docker Compose.
    """
    is_coro_fn = inspect.iscoroutinefunction(init_database)
    last_exc: Optional[Exception] = None

    for attempt in range(1, MAX_DB_INIT_ATTEMPTS + 1):
        try:
            if is_coro_fn:
                await init_database()
            else:
                # run blocking init in a thread to avoid blocking the event loop
                await anyio.to_thread.run_sync(init_database)

            _logger.info("Database initialization succeeded")
            break
        except Exception as exc:
            last_exc = exc
            _logger.warning(
                "Database init attempt %d/%d failed: %s",
                attempt,
                MAX_DB_INIT_ATTEMPTS,
                exc,
            )
            if attempt < MAX_DB_INIT_ATTEMPTS:
                await anyio.sleep(DB_INIT_DELAY_SEC)
            else:
                _logger.error(
                    "Database initialization failed after %d attempts", attempt
                )
                raise
    # Initialize Neo4j connection (best-effort). If driver isn't available or
    # connection fails, the adapter will fall back to a stub implementation.
    try:
        graph_adapter.connect(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    except Exception:
        _logger.exception(
            "Failed to initialize Neo4j adapter; continuing with stub/fallback"
        )
    try:
        yield
    finally:
        # close Neo4j on shutdown
        try:
            graph_adapter.close()
        except Exception:
            _logger.exception("Error closing Neo4j adapter during shutdown")


# Create FastAPI app with the lifespan manager
app = FastAPI(
    title="SmartMeal - Profile Management",
    version="1.0.0",
    description="Manage user profiles, dietary preferences, allergies",
    lifespan=lifespan,
)

# Include routers
app.include_router(router)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "profile-management"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
