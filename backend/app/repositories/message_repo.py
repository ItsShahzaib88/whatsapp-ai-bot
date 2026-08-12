"""
Message Repository — Message data access layer with conversation history.
"""

from datetime import datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository):
    """
    Repository for the 'messages' collection.
    Handles message history retrieval, status updates, and analytics queries.
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        super().__init__(db, "messages")

    async def get_conversation_history(
        self,
        contact_id: str,
        limit: int = 20,
        before_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get recent conversation messages for a contact.
        Returns messages in chronological order (oldest first).

        Args:
            contact_id: Contact's string ObjectId.
            limit: Max messages to return.
            before_id: If provided, fetch messages before this message ID (pagination).
        """
        filter_query: dict[str, Any] = {"contact_id": contact_id}
        if before_id:
            before_msg = await self.find_by_id(before_id)
            if before_msg:
                filter_query["created_at"] = {"$lt": before_msg["created_at"]}

        messages = await self.find_many(
            filter=filter_query,
            sort=[("created_at", DESCENDING)],
            limit=limit,
        )
        # Return in chronological order
        return list(reversed(messages))

    async def get_context_messages(
        self,
        contact_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get the most recent messages for AI context window.
        Returns list of {"role": "user/assistant", "content": str} dicts.
        """
        messages = await self.find_many(
            filter={"contact_id": contact_id},
            sort=[("created_at", DESCENDING)],
            limit=limit,
        )
        # Convert to AI message format, in chronological order
        result = []
        for msg in reversed(messages):
            role = "user" if msg["direction"] == "inbound" else "assistant"
            content = msg.get("voice_transcript") or msg.get("content", "")
            if content:
                result.append({"role": role, "content": content})
        return result

    async def update_status(self, wa_message_id: str, status: str) -> bool:
        """Update delivery status using WhatsApp message ID."""
        result = await self._collection.update_one(
            {"wa_message_id": wa_message_id},
            {
                "$set": {
                    "status": status,
                    "status_updated_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        return result.modified_count > 0

    async def get_failed_messages(self, max_retries: int = 3) -> list[dict[str, Any]]:
        """Get failed messages that haven't exceeded max retry attempts."""
        return await self.find_many(
            filter={
                "status": "failed",
                "direction": "outbound",
                "retry_count": {"$lt": max_retries},
            },
            sort=[("created_at", ASCENDING)],
            limit=50,
        )

    async def increment_retry_count(self, message_id: str) -> None:
        """Increment the retry counter for a failed message."""
        from bson import ObjectId
        if ObjectId.is_valid(message_id):
            await self._collection.update_one(
                {"_id": ObjectId(message_id)},
                {"$inc": {"retry_count": 1}, "$set": {"updated_at": datetime.utcnow()}},
            )

    async def get_analytics(
        self, days: int = 7
    ) -> dict[str, Any]:
        """Aggregate message analytics for dashboard stats."""
        since = datetime.utcnow() - timedelta(days=days)

        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "inbound": {"$sum": {"$cond": [{"$eq": ["$direction", "inbound"]}, 1, 0]}},
                    "outbound": {"$sum": {"$cond": [{"$eq": ["$direction", "outbound"]}, 1, 0]}},
                    "failed": {"$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}},
                    "voice": {"$sum": {"$cond": [{"$eq": ["$message_type", "voice"]}, 1, 0]}},
                }
            },
        ]
        results = await self.aggregate(pipeline)
        if results:
            r = results[0]
            r.pop("_id", None)
            return r
        return {"total": 0, "inbound": 0, "outbound": 0, "failed": 0, "voice": 0}

    async def get_daily_message_counts(self, days: int = 30) -> list[dict[str, Any]]:
        """Get daily message counts for chart data."""
        from datetime import timezone
        since = datetime.utcnow() - timedelta(days=days)
        pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$created_at"},
                        "month": {"$month": "$created_at"},
                        "day": {"$dayOfMonth": "$created_at"},
                    },
                    "count": {"$sum": 1},
                    "inbound": {"$sum": {"$cond": [{"$eq": ["$direction", "inbound"]}, 1, 0]}},
                    "outbound": {"$sum": {"$cond": [{"$eq": ["$direction", "outbound"]}, 1, 0]}},
                }
            },
            {"$sort": {"_id": ASCENDING}},
        ]
        return await self.aggregate(pipeline)
