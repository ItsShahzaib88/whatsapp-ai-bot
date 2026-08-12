"""
Authentication Service — Login, registration, token management.
"""

from datetime import datetime
from typing import Any

import structlog

from app.core.exceptions import DuplicateException, InvalidCredentialsException
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.repositories.user_repo import UserRepository

logger = structlog.get_logger(__name__)


class AuthService:
    """
    Service for admin user authentication operations.
    Handles registration, login, and token generation.
    """

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    async def register(
        self, name: str, email: str, password: str
    ) -> dict[str, Any]:
        """
        Register a new admin user.
        Raises DuplicateException if email already exists.
        """
        existing = await self._user_repo.find_by_email(email)
        if existing:
            raise DuplicateException(detail="An account with this email already exists")

        user_data = {
            "name": name,
            "email": email.lower().strip(),
            "hashed_password": hash_password(password),
            "is_active": True,
            "is_superuser": False,
            "theme": "dark",
        }
        user_id = await self._user_repo.insert_one(user_data)
        user_data["id"] = user_id
        logger.info("New admin user registered", email=email, user_id=user_id)
        return user_data

    async def login(self, email: str, password: str) -> dict[str, Any]:
        """
        Authenticate a user and return JWT tokens.

        Returns:
            Dict with access_token, refresh_token, and user info.

        Raises:
            InvalidCredentialsException: On wrong email or password.
        """
        user = await self._user_repo.find_by_email(email)
        if not user:
            raise InvalidCredentialsException()

        if not verify_password(password, user["hashed_password"]):
            raise InvalidCredentialsException()

        if not user.get("is_active", True):
            raise InvalidCredentialsException(detail="Account is disabled")

        # Update last login
        await self._user_repo.update_last_login(user["id"])

        # Generate tokens
        token_data = {"sub": user["id"], "email": user["email"]}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        logger.info("User logged in", user_id=user["id"], email=email)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "theme": user.get("theme", "dark"),
                "is_superuser": user.get("is_superuser", False),
            },
        }

    async def ensure_default_admin(self) -> None:
        """
        Create the default admin account if no users exist.
        Called during application startup.
        """
        from app.core.config import settings
        count = await self._user_repo.count()
        if count == 0:
            await self.register(
                name=settings.ADMIN_NAME,
                email=settings.ADMIN_EMAIL,
                password=settings.ADMIN_PASSWORD,
            )
            logger.info(
                "Default admin created",
                email=settings.ADMIN_EMAIL,
            )
