"""
Consolidated middleware for the SmartMeal API
"""

import time
import logging
from datetime import datetime
from uuid import uuid4
from decimal import Decimal

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.exceptions import ServiceValidationError, NotFoundError

logger = logging.getLogger("smartmeal.middleware")


# ============================================================================
# Helper Functions
# ============================================================================


def make_serializable(obj):
    """Convert objects to JSON-serializable format"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_serializable(item) for item in obj]
    return obj


# ============================================================================
# Request Logging Middleware
# ============================================================================


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests and responses"""

    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid4())
        request.state.request_id = request_id

        # Log request
        logger.info(
            f"Request started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "client": request.client.host if request.client else None,
            },
        )

        # Process request and measure time
        start_time = time.time()

        try:
            response: Response = await call_next(request)
            process_time = time.time() - start_time

            # Log response
            logger.info(
                f"Request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "url": str(request.url),
                    "status_code": response.status_code,
                    "process_time": f"{process_time:.4f}s",
                },
            )

            # Add custom headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}"

            return response

        except Exception as exc:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "url": str(request.url),
                    "error": str(exc),
                    "process_time": f"{process_time:.4f}s",
                },
                exc_info=True,
            )
            raise


# ============================================================================
# Error Handlers
# ============================================================================


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors"""
    logger.warning(f"Validation error on {request.url}: {exc.errors()}")

    # Convert errors to JSON-serializable format (handles Decimal, etc.)
    serializable_errors = make_serializable(exc.errors())

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": serializable_errors,
            },
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions"""
    logger.warning(f"HTTP {exc.status_code} on {request.url}: {exc.detail}")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
            },
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def service_validation_exception_handler(
    request: Request, exc: ServiceValidationError
):
    """Handle service validation errors"""
    logger.warning(f"Service validation error on {request.url}: {str(exc)}")

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": {
                "code": "SERVICE_VALIDATION_ERROR",
                "message": str(exc),
            },
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def not_found_exception_handler(request: Request, exc: NotFoundError):
    """Handle not found errors"""
    logger.warning(f"Resource not found on {request.url}: {str(exc)}")

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "success": False,
            "error": {
                "code": "NOT_FOUND",
                "message": str(exc),
            },
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    logger.exception(f"Unexpected error on {request.url}: {str(exc)}")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
            },
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
