"""
Security utilities — JWT tokens, password hashing, verification.
Uses python-jose for JWT and passlib/bcrypt for password security.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        data: Payload data to encode in the token.
        expires_delta: Custom expiry duration. Defaults to settings value.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(data: dict[str, Any]) -> str:
    """
    Create a signed JWT refresh token with longer expiry.

    Args:
        data: Payload data to encode.

    Returns:
        Encoded JWT refresh token string.
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict[str, Any] | None:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT string to decode.

    Returns:
        Decoded payload dict, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as e:
        logger.warning("JWT decode failed", error=str(e))
        return None


def verify_webhook_token(token: str) -> bool:
    """
    Verify WhatsApp webhook verification token.

    Args:
        token: Token received from WhatsApp verification request.

    Returns:
        True if token matches configured verify token.
    """
    return token == settings.WHATSAPP_VERIFY_TOKEN
