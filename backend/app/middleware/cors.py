"""
CORS Middleware Configuration
Configures Cross-Origin Resource Sharing for the FastAPI application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


def add_cors_middleware(app: FastAPI) -> None:
    """
    Add CORS middleware to the FastAPI application.

    Allows the frontend (Next.js) to communicate with the backend API.
    In production, only the configured FRONTEND_URL is allowed.
    """
    origins = settings.CORS_ORIGINS

    # Always include the configured frontend URL
    if settings.FRONTEND_URL not in origins:
        origins.append(settings.FRONTEND_URL)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Request-ID",
            "X-API-Key",
        ],
        expose_headers=["X-Request-ID", "X-RateLimit-Remaining"],
        max_age=600,  # Cache preflight for 10 minutes
    )
