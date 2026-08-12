"""
MongoDB async connection management using Motor driver.
Handles connection pooling, index creation, and graceful shutdown.
"""

from typing import Any

import structlog
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Module-level client and database references
_client: AsyncIOMotorClient | None = None  # type: ignore[type-arg]
_database: AsyncIOMotorDatabase | None = None  # type: ignore[type-arg]


async def connect_mongo() -> None:
    """
    Initialize the MongoDB connection and create required indexes.
    Called during application startup via the lifespan context manager.
    """
    global _client, _database

    _client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        maxPoolSize=20,
        minPoolSize=5,
        connectTimeoutMS=5000,
        serverSelectionTimeoutMS=5000,
    )
    _database = _client[settings.MONGODB_DB_NAME]

    # Verify connection
    await _client.admin.command("ping")
    logger.info("MongoDB connection established", db=settings.MONGODB_DB_NAME)

    # Create all indexes
    await _create_indexes()


async def close_mongo() -> None:
    """
    Close the MongoDB connection pool.
    Called during application shutdown.
    """
    global _client, _database
    if _client:
        _client.close()
        _client = None
        _database = None
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """
    Return the active database instance.
    Raises RuntimeError if called before connect_mongo().
    """
    if _database is None:
        raise RuntimeError("MongoDB is not connected. Call connect_mongo() first.")
    return _database


async def _create_indexes() -> None:
    """
    Create all MongoDB collection indexes for optimal query performance.
    Uses IndexModel for batch index creation.
    """
    db = get_database()

    # ---- Users collection ----
    await db.users.create_indexes([
        IndexModel([("email", ASCENDING)], unique=True, name="email_unique"),
        IndexModel([("created_at", DESCENDING)], name="created_at_desc"),
    ])

    # ---- Contacts collection ----
    await db.contacts.create_indexes([
        IndexModel([("phone_number", ASCENDING)], unique=True, name="phone_unique"),
        IndexModel([("name", ASCENDING)], name="name_asc"),
        IndexModel([("created_at", DESCENDING)], name="created_at_desc"),
        IndexModel([("is_active", ASCENDING)], name="is_active"),
    ])

    # ---- Messages collection ----
    await db.messages.create_indexes([
        IndexModel([("contact_id", ASCENDING), ("created_at", DESCENDING)], name="contact_time"),
        IndexModel([("wa_message_id", ASCENDING)], unique=True, sparse=True, name="wa_msg_id"),
        IndexModel([("status", ASCENDING)], name="status"),
        IndexModel([("direction", ASCENDING)], name="direction"),
        IndexModel([("created_at", DESCENDING)], name="created_at_desc"),
    ])

    # ---- ConversationMemory collection ----
    await db.conversation_memory.create_indexes([
        IndexModel([("contact_id", ASCENDING)], unique=True, name="contact_unique"),
        IndexModel([("updated_at", DESCENDING)], name="updated_at_desc"),
    ])

    # ---- Personalities collection ----
    await db.personalities.create_indexes([
        IndexModel([("name", ASCENDING)], unique=True, name="name_unique"),
        IndexModel([("is_default", ASCENDING)], name="is_default"),
    ])

    # ---- AISettings collection ----
    await db.ai_settings.create_indexes([
        IndexModel([("created_at", DESCENDING)], name="created_at_desc"),
    ])

    # ---- Schedules collection ----
    await db.schedules.create_indexes([
        IndexModel([("is_active", ASCENDING)], name="is_active"),
        IndexModel([("mode", ASCENDING)], name="mode"),
    ])

    # ---- Logs collection ----
    await db.logs.create_indexes([
        IndexModel([("created_at", DESCENDING)], name="created_at_desc"),
        IndexModel([("level", ASCENDING)], name="level"),
        IndexModel([("action", ASCENDING)], name="action"),
        # TTL index: auto-delete logs older than 90 days
        IndexModel(
            [("created_at", ASCENDING)],
            expireAfterSeconds=7_776_000,
            name="ttl_90_days",
        ),
    ])

    logger.info("MongoDB indexes created/verified")
