"""
Authentication Router — Login, register, refresh, profile endpoints.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.api.v1.dependencies.auth import CurrentUser
from app.core.exceptions import AuthException
from app.core.security import decode_token
from app.database.mongodb import get_database
from app.repositories.user_repo import UserRepository
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth")


def get_auth_service() -> AuthService:
    db = get_database()
    return AuthService(UserRepository(db))


@router.post("/login")
async def login(
    body: dict[str, Any],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    """
    Authenticate admin user and return JWT tokens.
    Body: {"email": "...", "password": "..."}
    """
    email = body.get("email", "")
    password = body.get("password", "")

    if not email or not password:
        raise AuthException(detail="Email and password are required")

    result = await auth_service.login(email, password)
    return {"success": True, "data": result}


@router.post("/register")
async def register(
    body: dict[str, Any],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    """
    Register a new admin user.
    Body: {"name": "...", "email": "...", "password": "..."}
    """
    name = body.get("name", "")
    email = body.get("email", "")
    password = body.get("password", "")

    if not all([name, email, password]):
        raise AuthException(detail="Name, email and password are required")

    if len(password) < 8:
        raise AuthException(detail="Password must be at least 8 characters")

    user = await auth_service.register(name, email, password)
    return {"success": True, "message": "Account created successfully", "data": {"id": user["id"]}}


@router.get("/me")
async def get_profile(current_user: CurrentUser) -> dict[str, Any]:
    """Get the authenticated admin's profile."""
    return {
        "success": True,
        "data": {
            "id": current_user["id"],
            "name": current_user["name"],
            "email": current_user["email"],
            "theme": current_user.get("theme", "dark"),
            "is_superuser": current_user.get("is_superuser", False),
            "last_login": str(current_user.get("last_login", "")),
        },
    }


@router.post("/refresh")
async def refresh_token(body: dict[str, Any]) -> dict[str, Any]:
    """Refresh access token using a valid refresh token."""
    from app.core.security import create_access_token
    token = body.get("refresh_token", "")
    if not token:
        raise AuthException(detail="Refresh token required")

    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise AuthException(detail="Invalid or expired refresh token")

    access_token = create_access_token({"sub": payload["sub"], "email": payload["email"]})
    return {"success": True, "data": {"access_token": access_token, "token_type": "bearer"}}


@router.patch("/me/theme")
async def update_theme(
    body: dict[str, Any],
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Update user theme preference (dark/light)."""
    theme = body.get("theme", "dark")
    if theme not in ("dark", "light"):
        raise AuthException(detail="Theme must be 'dark' or 'light'")

    db = get_database()
    repo = UserRepository(db)
    await repo.update_theme(current_user["id"], theme)
    return {"success": True, "message": "Theme updated"}
