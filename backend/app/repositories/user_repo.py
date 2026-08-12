"""
User Repository — Admin user data access layer.
"""

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """
    Repository for the 'users' collection.
    Provides user-specific query methods beyond the generic CRUD.
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        super().__init__(db, "users")

    async def find_by_email(self, email: str) -> dict[str, Any] | None:
        """Find a user by their email address (case-insensitive)."""
        return await self.find_one({"email": email.lower().strip()})

    async def update_last_login(self, user_id: str) -> None:
        """Update last login timestamp and increment login counter."""
        from datetime import datetime
        await self._collection.update_one(
            {"_id": __import__("bson").ObjectId(user_id)},
            {
                "$set": {"last_login": datetime.utcnow()},
                "$inc": {"login_count": 1},
            },
        )

    async def update_theme(self, user_id: str, theme: str) -> bool:
        """Update user dashboard theme preference."""
        return await self.update_one(user_id, {"theme": theme})
