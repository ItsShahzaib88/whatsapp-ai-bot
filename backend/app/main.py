"""
AI WhatsApp Assistant — FastAPI Application Factory
Handles app creation, middleware registration, router mounting, and lifespan.
Serves HTML Admin Dashboard at /dashboard.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.routers import auth, contacts, health, webhook
from app.api.v1.routers.messages import (
    messages_router,
    personalities_router,
    ai_settings_router,
    analytics_router,
    logs_router,
)
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import configure_logging
from app.database.mongodb import close_mongo, connect_mongo
from app.middleware.cors import add_cors_middleware
from app.middleware.logging import RequestLoggingMiddleware

logger = structlog.get_logger(__name__)

# Path to the HTML dashboard directory (relative to where uvicorn is run — the backend/ folder)
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "..", "dashboard_html")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.
    Handles startup and shutdown events for DB connections, caches, etc.
    """
    # --- STARTUP ---
    configure_logging()
    logger.info("Starting AI WhatsApp Assistant", version=settings.APP_VERSION)

    await connect_mongo()
    logger.info("MongoDB connected successfully")

    # Auto-create default admin user if none exists
    try:
        from app.database.mongodb import get_database
        from app.repositories.user_repo import UserRepository
        from app.services.auth_service import AuthService

        db = get_database()
        auth_service = AuthService(UserRepository(db))
        await auth_service.ensure_default_admin()
    except Exception as e:
        logger.warning("Could not ensure default admin", error=str(e))

    # Auto-create default personality if none exists
    try:
        from app.database.mongodb import get_database
        from app.repositories.memory_repo import PersonalityRepository

        db = get_database()
        personality_repo = PersonalityRepository(db)
        default = await personality_repo.get_default()
        if not default:
            await personality_repo.insert_one({
                "name": "assistant",
                "display_name": "Friendly Assistant",
                "tone": "friendly",
                "language_style": "balanced",
                "reply_length": "medium",
                "emoji_usage": "moderate",
                "persona_instructions": (
                    "You are a helpful, warm, and intelligent AI assistant. "
                    "Be conversational, concise, and always culturally respectful. "
                    "Support English, Urdu, and Roman Urdu naturally."
                ),
                "greeting_style": "Warm and welcoming",
                "signoff_style": "Helpful and encouraging",
                "avoid_topics": [],
                "is_default": True,
                "is_active": True,
            })
            logger.info("Default personality created")
    except Exception as e:
        logger.warning("Could not ensure default personality", error=str(e))

    # Ensure media upload directory exists
    try:
        os.makedirs(settings.MEDIA_UPLOAD_DIR, exist_ok=True)
    except Exception:
        pass

    logger.info("Application startup complete")

    yield

    # --- SHUTDOWN ---
    logger.info("Shutting down AI WhatsApp Assistant...")
    await close_mongo()
    logger.info("Shutdown complete")


def create_application() -> FastAPI:
    """
    Factory function to create and configure the FastAPI application.
    Uses the factory pattern for testability and clean separation of concerns.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Enterprise-grade AI WhatsApp Assistant with multi-provider AI, "
            "per-contact memory, personality system, and voice support."
        ),
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # ---- Middleware (order matters: first added = outermost) ----
    add_cors_middleware(app)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )

    # ---- Exception Handlers ----
    @app.exception_handler(AppException)
    async def app_exception_handler(request, exc: AppException) -> JSONResponse:
        logger.warning(
            "Application exception",
            status_code=exc.status_code,
            detail=exc.detail,
            path=str(request.url),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": exc.detail, "code": exc.code},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception", error=str(exc), path=str(request.url))
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error",
                "code": "INTERNAL_ERROR",
            },
        )

    # ---- API Routers ----
    api_prefix = "/api/v1"

    app.include_router(health.router, prefix=api_prefix, tags=["Health"])
    app.include_router(auth.router, prefix=api_prefix, tags=["Authentication"])
    app.include_router(webhook.router, prefix=api_prefix, tags=["WhatsApp Webhook"])
    app.include_router(contacts.router, prefix=api_prefix, tags=["Contacts"])
    app.include_router(messages_router, prefix=api_prefix, tags=["Messages"])
    app.include_router(personalities_router, prefix=api_prefix, tags=["Personalities"])
    app.include_router(ai_settings_router, prefix=api_prefix, tags=["AI Settings"])
    app.include_router(analytics_router, prefix=api_prefix, tags=["Analytics"])
    app.include_router(logs_router, prefix=api_prefix, tags=["Logs"])

    # ---- HTML Admin Dashboard ----
    dashboard_path = os.path.abspath(DASHBOARD_DIR)
    if os.path.isdir(dashboard_path):
        app.mount(
            "/dashboard",
            StaticFiles(directory=dashboard_path, html=True),
            name="dashboard",
        )
        logger.info("Admin dashboard mounted", path=dashboard_path)

    return app


# Application instance (used by uvicorn)
app = create_application()
