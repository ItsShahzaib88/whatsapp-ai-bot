"""
JWT Authentication Middleware and Bearer Token Extractor
Provides the get_current_user dependency for protected routes.
"""

from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthException, TokenExpiredException
from app.core.security import decode_token
from app.database.mongodb import get_database
from app.repositories.user_repo import UserRepository

logger = structlog.get_logger(__name__)

# Bearer token extractor scheme
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> dict:
    """
    FastAPI dependency that extracts and validates the JWT bearer token.
    Returns the decoded user payload if valid.

    Raises:
        AuthException: If token is missing or invalid.
        TokenExpiredException: If token has expired.
    """
    if not credentials:
        raise AuthException(detail="Authorization header missing")

    payload = decode_token(credentials.credentials)

    if payload is None:
        raise TokenExpiredException()

    if payload.get("type") != "access":
        raise AuthException(detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthException(detail="Token missing subject claim")

    # Verify user still exists in DB
    db = get_database()
    repo = UserRepository(db)
    user = await repo.find_by_id(user_id)

    if not user:
        raise AuthException(detail="User account not found")

    if not user.get("is_active", True):
        raise AuthException(detail="User account is disabled")

    logger.debug("User authenticated", user_id=user_id)
    return user


# Type alias for cleaner dependency injection in route handlers
CurrentUser = Annotated[dict, Depends(get_current_user)]
