"""
Messages, Personalities, AI Settings, Analytics, and Logs Routers
"""

from typing import Any

from fastapi import APIRouter, Query

from app.api.v1.dependencies.auth import CurrentUser
from app.core.exceptions import NotFoundException
from app.database.mongodb import get_database
from app.repositories.memory_repo import PersonalityRepository, LogRepository
from app.repositories.message_repo import MessageRepository

# ---- Messages Router ----
router = APIRouter()

messages_router = APIRouter(prefix="/messages")

@messages_router.get("")
async def list_messages(
    _: CurrentUser,
    contact_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    direction: str | None = Query(default=None),
) -> dict[str, Any]:
    """Get messages with optional contact and direction filter."""
    db = get_database()
    repo = MessageRepository(db)
    skip = (page - 1) * limit

    filter_q: dict[str, Any] = {}
    if contact_id:
        filter_q["contact_id"] = contact_id
    if direction:
        filter_q["direction"] = direction

    messages = await repo.find_many(
        filter=filter_q,
        sort=[("created_at", -1)],
        skip=skip,
        limit=limit,
    )
    total = await repo.count(filter_q)

    return {
        "success": True,
        "data": messages,
        "pagination": {"page": page, "limit": limit, "total": total},
    }


@messages_router.get("/conversation/{contact_id}")
async def get_conversation(
    contact_id: str,
    _: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    before_id: str | None = Query(default=None),
) -> dict[str, Any]:
    """Get paginated conversation history for a contact."""
    db = get_database()
    repo = MessageRepository(db)
    messages = await repo.get_conversation_history(
        contact_id=contact_id, limit=limit, before_id=before_id
    )
    return {"success": True, "data": messages}


# ---- Personalities Router ----
personalities_router = APIRouter(prefix="/personalities")


@personalities_router.get("")
async def list_personalities(_: CurrentUser) -> dict[str, Any]:
    db = get_database()
    repo = PersonalityRepository(db)
    personalities = await repo.get_all_active()
    return {"success": True, "data": personalities}


@personalities_router.post("")
async def create_personality(body: dict[str, Any], _: CurrentUser) -> dict[str, Any]:
    db = get_database()
    repo = PersonalityRepository(db)
    required = {"name", "display_name"}
    if not required.issubset(body.keys()):
        raise ValueError("name and display_name are required")
    new_id = await repo.insert_one(body)
    return {"success": True, "data": {"id": new_id}}


@personalities_router.put("/{personality_id}")
async def update_personality(
    personality_id: str, body: dict[str, Any], _: CurrentUser
) -> dict[str, Any]:
    db = get_database()
    repo = PersonalityRepository(db)
    existing = await repo.find_by_id(personality_id)
    if not existing:
        raise NotFoundException(detail="Personality not found")
    await repo.update_one(personality_id, body)
    return {"success": True, "message": "Personality updated"}


@personalities_router.delete("/{personality_id}")
async def delete_personality(personality_id: str, _: CurrentUser) -> dict[str, Any]:
    db = get_database()
    repo = PersonalityRepository(db)
    await repo.delete_one(personality_id)
    return {"success": True, "message": "Personality deleted"}


# ---- AI Settings Router ----
ai_settings_router = APIRouter(prefix="/ai-settings")


@ai_settings_router.get("")
async def get_ai_settings(_: CurrentUser) -> dict[str, Any]:
    from app.services.ai_service import get_ai_service
    ai_service = get_ai_service()
    return {
        "success": True,
        "data": {
            "active_provider": ai_service.get_active_provider_name(),
            "available_providers": ai_service.get_available_providers(),
        },
    }


@ai_settings_router.patch("")
async def update_ai_settings(body: dict[str, Any], _: CurrentUser) -> dict[str, Any]:
    from app.services.ai_service import get_ai_service
    ai_service = get_ai_service()
    if "active_provider" in body:
        ai_service.set_active_provider(body["active_provider"])
    return {"success": True, "message": "AI settings updated"}


# ---- Analytics Router ----
analytics_router = APIRouter(prefix="/analytics")


@analytics_router.get("/stats")
async def get_stats(_: CurrentUser, days: int = Query(default=7, ge=1, le=90)) -> dict[str, Any]:
    db = get_database()
    msg_repo = MessageRepository(db)
    from app.repositories.contact_repo import ContactRepository
    contact_repo = ContactRepository(db)

    msg_stats = await msg_repo.get_analytics(days=days)
    total_contacts = await contact_repo.count({"is_active": True})
    ai_contacts = await contact_repo.count({"is_active": True, "ai_enabled": True})
    daily_counts = await msg_repo.get_daily_message_counts(days=days)

    return {
        "success": True,
        "data": {
            "messages": msg_stats,
            "contacts": {"total": total_contacts, "ai_enabled": ai_contacts},
            "daily_counts": daily_counts,
            "period_days": days,
        },
    }


# ---- Logs Router ----
logs_router = APIRouter(prefix="/logs")


@logs_router.get("")
async def get_logs(
    _: CurrentUser,
    level: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    db = get_database()
    repo = LogRepository(db)
    skip = (page - 1) * limit
    logs = await repo.get_recent_logs(level=level, limit=limit, skip=skip)
    return {"success": True, "data": logs}
