"""
Redis async connection management using redis-py with asyncio support.
Provides connection pooling, health checks, and utility methods.
"""

import structlog
import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Module-level Redis client reference
_redis: Redis | None = None  # type: ignore[type-arg]


async def connect_redis() -> None:
    """
    Initialize the Redis connection pool.
    Called during application startup.
    """
    global _redis

    connection_kwargs: dict = {
        "decode_responses": True,
        "max_connections": 20,
        "socket_timeout": 5,
        "socket_connect_timeout": 5,
        "retry_on_timeout": True,
    }

    if settings.REDIS_PASSWORD:
        connection_kwargs["password"] = settings.REDIS_PASSWORD

    _redis = aioredis.from_url(settings.REDIS_URL, **connection_kwargs)

    # Verify connection
    await _redis.ping()
    logger.info("Redis connection established", url=settings.REDIS_URL)


async def close_redis() -> None:
    """
    Close the Redis connection pool.
    Called during application shutdown.
    """
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed")


def get_redis() -> Redis:  # type: ignore[type-arg]
    """
    Return the active Redis client instance.
    Raises RuntimeError if called before connect_redis().
    """
    if _redis is None:
        raise RuntimeError("Redis is not connected. Call connect_redis() first.")
    return _redis


async def redis_set(key: str, value: str, expire: int | None = None) -> None:
    """
    Set a key-value pair in Redis with optional TTL.

    Args:
        key: Redis key.
        value: String value to store.
        expire: Optional TTL in seconds.
    """
    client = get_redis()
    if expire:
        await client.setex(key, expire, value)
    else:
        await client.set(key, value)


async def redis_get(key: str) -> str | None:
    """
    Get a value from Redis by key.

    Args:
        key: Redis key to fetch.

    Returns:
        String value or None if not found.
    """
    client = get_redis()
    return await client.get(key)


async def redis_delete(key: str) -> None:
    """Delete a key from Redis."""
    client = get_redis()
    await client.delete(key)


async def redis_increment(key: str, expire: int | None = None) -> int:
    """
    Atomically increment a counter in Redis.

    Args:
        key: Redis key for the counter.
        expire: Set TTL only if counter is new (first increment).

    Returns:
        New counter value after increment.
    """
    client = get_redis()
    value = await client.incr(key)
    if value == 1 and expire:
        await client.expire(key, expire)
    return value
