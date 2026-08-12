"""
Memory, Personality, and Log Repositories
"""

from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from app.repositories.base import BaseRepository


class MemoryRepository(BaseRepository):
    """
    Repository for the 'conversation_memory' collection.
    One memory document per contact, upserted after each conversation.
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        super().__init__(db, "conversation_memory")

    async def find_by_contact(self, contact_id: str) -> dict[str, Any] | None:
        """Get memory document for a specific contact."""
        return await self.find_one({"contact_id": contact_id})

    async def upsert_memory(
        self, contact_id: str, memory_data: dict[str, Any]
    ) -> str:
        """Create or update memory for a contact."""
        memory_data["last_memory_update"] = datetime.utcnow()
        return await self.upsert_one(
            {"contact_id": contact_id},
            memory_data,
        )

    async def increment_conversation_count(self, contact_id: str) -> None:
        """Increment total conversation count for memory tracking."""
        from bson import ObjectId
        await self._collection.update_one(
            {"contact_id": contact_id},
            {
                "$inc": {"total_conversations": 1},
                "$set": {
                    "last_conversation_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                },
            },
        )


class PersonalityRepository(BaseRepository):
    """
    Repository for the 'personalities' collection.
    Manages AI personality templates.
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        super().__init__(db, "personalities")

    async def find_by_name(self, name: str) -> dict[str, Any] | None:
        """Find a personality by its unique name."""
        return await self.find_one({"name": name})

    async def get_default(self) -> dict[str, Any] | None:
        """Get the default personality (fallback when contact has none assigned)."""
        return await self.find_one({"is_default": True, "is_active": True})

    async def get_all_active(self) -> list[dict[str, Any]]:
        """Get all active personality templates."""
        return await self.find_many(
            filter={"is_active": True},
            sort=[("name", 1)],
            limit=100,
        )


class LogRepository(BaseRepository):
    """
    Repository for the 'logs' collection.
    Provides log writing and querying for the admin dashboard.
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        super().__init__(db, "logs")

    async def write_log(
        self,
        level: str,
        action: str,
        message: str,
        **kwargs: Any,
    ) -> str:
        """
        Write a structured log entry.

        Args:
            level: Log level (INFO, WARNING, ERROR, etc.)
            action: Action identifier string.
            message: Human-readable log message.
            **kwargs: Additional context fields (contact_id, request_id, etc.)
        """
        log_data = {
            "level": level.upper(),
            "action": action,
            "message": message,
            **kwargs,
        }
        return await self.insert_one(log_data)

    async def get_recent_logs(
        self,
        level: str | None = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        """Get recent logs with optional level filtering."""
        filter_query: dict[str, Any] = {}
        if level:
            filter_query["level"] = level.upper()
        return await self.find_many(
            filter=filter_query,
            sort=[("created_at", DESCENDING)],
            skip=skip,
            limit=limit,
        )
