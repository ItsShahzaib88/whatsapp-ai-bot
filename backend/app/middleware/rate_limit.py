"""
Rate Limiting Middleware — Sliding Window Algorithm via Redis
Limits requests per-IP per minute and per hour.
"""

import time

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.database.redis import get_redis

logger = structlog.get_logger(__name__)

# Paths exempt from rate limiting (e.g., health checks, webhook)
EXEMPT_PATHS = {"/api/v1/health", "/api/v1/webhook"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter using Redis atomic counters.
    Enforces per-IP limits: X requests/minute and Y requests/hour.
    Returns 429 with retry-after header when limit is exceeded.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for exempt paths
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        # Get client IP (respect X-Forwarded-For behind Nginx)
        client_ip = self._get_client_ip(request)

        try:
            redis = get_redis()
            now = int(time.time())

            # ---- Per-minute limit ----
            minute_key = f"ratelimit:minute:{client_ip}:{now // 60}"
            minute_count = await redis.incr(minute_key)
            if minute_count == 1:
                await redis.expire(minute_key, 60)

            if minute_count > settings.RATE_LIMIT_PER_MINUTE:
                logger.warning(
                    "Rate limit exceeded (minute)",
                    ip=client_ip,
                    count=minute_count,
                    path=request.url.path,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": "Too many requests. Please wait a minute.",
                        "code": "RATE_LIMIT_EXCEEDED",
                    },
                    headers={"Retry-After": "60"},
                )

            # ---- Per-hour limit ----
            hour_key = f"ratelimit:hour:{client_ip}:{now // 3600}"
            hour_count = await redis.incr(hour_key)
            if hour_count == 1:
                await redis.expire(hour_key, 3600)

            if hour_count > settings.RATE_LIMIT_PER_HOUR:
                logger.warning(
                    "Rate limit exceeded (hour)",
                    ip=client_ip,
                    count=hour_count,
                    path=request.url.path,
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": "Hourly request limit exceeded.",
                        "code": "RATE_LIMIT_EXCEEDED",
                    },
                    headers={"Retry-After": "3600"},
                )

            response = await call_next(request)
            # Attach remaining quota headers
            response.headers["X-RateLimit-Limit-Minute"] = str(settings.RATE_LIMIT_PER_MINUTE)
            response.headers["X-RateLimit-Remaining-Minute"] = str(
                max(0, settings.RATE_LIMIT_PER_MINUTE - minute_count)
            )
            return response

        except Exception as e:
            # Don't block requests if Redis is temporarily unavailable
            logger.error("Rate limiter error (allowing request)", error=str(e))
            return await call_next(request)

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract real client IP, respecting proxy headers."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
