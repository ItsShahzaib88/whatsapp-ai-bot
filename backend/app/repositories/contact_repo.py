"""
Contact Repository — WhatsApp contact data access layer.
"""

from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.repositories.base import BaseRepository


class ContactRepository(BaseRepository):
    """
    Repository for the 'contacts' collection.
    Provides contact-specific queries for search, filtering, and stats.
    """

    def __init__(self, db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
        super().__init__(db, "contacts")

    async def find_by_phone_and_bot(self, phone_number: str, bot_id: str) -> dict[str, Any] | None:
        """Find a contact by their WhatsApp phone number and the bot they are talking to."""
        return await self.find_one({"phone_number": phone_number, "bot_id": bot_id})

    async def get_or_create_by_phone(
        self, phone_number: str, bot_id: str, wa_name: str | None = None
    ) -> tuple[dict[str, Any], bool]:
        """
        Get a contact by phone number and bot_id, creating them if they don't exist.

        Returns:
            Tuple of (contact_dict, created: bool)
        """
        existing = await self.find_by_phone_and_bot(phone_number, bot_id)
        if existing:
            return existing, False

        # Create new contact
        now = datetime.utcnow()
        contact_data: dict[str, Any] = {
            "phone_number": phone_number,
            "bot_id": bot_id,
            "name": wa_name or "Unknown",
            "wa_name": wa_name,
            "is_active": True,
            "ai_enabled": True,
            "auto_reply_mode": "ai",
            "voice_reply_enabled": False,
            "preferred_language": "en",
            "total_messages_sent": 0,
            "total_messages_received": 0,
            "tags": [],
            "created_at": now,
            "updated_at": now,
        }
        new_id = await self.insert_one(contact_data)
        contact_data["id"] = new_id
        return contact_data, True

    async def search(
        self,
        query: str,
        skip: int = 0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Full-text search across contact name and phone number."""
        filter_query: dict[str, Any] = {
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"phone_number": {"$regex": query, "$options": "i"}},
                {"nickname": {"$regex": query, "$options": "i"}},
                {"tags": {"$in": [query.lower()]}},
            ]
        }
        return await self.find_many(
            filter=filter_query,
            sort=[("last_message_at", DESCENDING)],
            skip=skip,
            limit=limit,
        )

    async def increment_message_count(
        self, contact_id: str, direction: str
    ) -> None:
        """Increment sent or received message counter atomically."""
        from bson import ObjectId
        field = (
            "total_messages_sent"
            if direction == "outbound"
            else "total_messages_received"
        )
        await self._collection.update_one(
            {"_id": ObjectId(contact_id)},
            {
                "$inc": {field: 1},
                "$set": {"last_message_at": datetime.utcnow().isoformat()},
            },
        )

    async def get_active_ai_contacts(self) -> list[dict[str, Any]]:
        """Return all contacts with AI replies enabled."""
        return await self.find_many(
            filter={"is_active": True, "ai_enabled": True, "is_blocked": False},
            limit=1000,
        )
