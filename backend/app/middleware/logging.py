"""
Request/Response Logging Middleware
Logs all incoming requests and outgoing responses with timing information.
Adds unique X-Request-ID header for distributed tracing.
"""

import time
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every HTTP request with method, path, status code, and duration.
    Injects a unique request ID for tracing through logs.
    Skips health check endpoint to avoid log noise.
    """

    SKIP_PATHS = {"/api/v1/health"}

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        # Bind request context to structlog
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )

        response = await call_next(request)

        # Calculate response time
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Skip logging for health checks
        if request.url.path not in self.SKIP_PATHS:
            log_method = logger.warning if response.status_code >= 400 else logger.info
            log_method(
                "Request processed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

        # Attach request ID to response headers
        response.headers["X-Request-ID"] = request_id
        return response
