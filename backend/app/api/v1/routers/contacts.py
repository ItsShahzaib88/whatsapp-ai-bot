"""
Contacts Router — CRUD, search, memory, personality management.
"""

from typing import Any

from fastapi import APIRouter, Query

from app.api.v1.dependencies.auth import CurrentUser
from app.core.exceptions import ContactNotFoundException
from app.database.mongodb import get_database
from app.repositories.contact_repo import ContactRepository
from app.repositories.memory_repo import MemoryRepository, PersonalityRepository

router = APIRouter(prefix="/contacts")


@router.get("")
async def list_contacts(
    _: CurrentUser,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: str = Query(default=""),
    ai_enabled: bool | None = Query(default=None),
) -> dict[str, Any]:
    """List contacts with pagination and optional search/filter."""
    db = get_database()
    repo = ContactRepository(db)
    skip = (page - 1) * limit

    if search:
        contacts = await repo.search(search, skip=skip, limit=limit)
        total = len(contacts)
    else:
        filter_q: dict[str, Any] = {}
        if ai_enabled is not None:
            filter_q["ai_enabled"] = ai_enabled
        contacts = await repo.find_many(
            filter=filter_q,
            sort=[("last_message_at", -1)],
            skip=skip,
            limit=limit,
        )
        total = await repo.count(filter_q)

    return {
        "success": True,
        "data": contacts,
        "pagination": {"page": page, "limit": limit, "total": total},
    }


@router.get("/{contact_id}")
async def get_contact(contact_id: str, _: CurrentUser) -> dict[str, Any]:
    """Get a single contact by ID with their memory and personality."""
    db = get_database()
    repo = ContactRepository(db)
    contact = await repo.find_by_id(contact_id)
    if not contact:
        raise ContactNotFoundException()

    memory_repo = MemoryRepository(db)
    memory = await memory_repo.find_by_contact(contact_id)

    personality = None
    if contact.get("personality_id"):
        p_repo = PersonalityRepository(db)
        personality = await p_repo.find_by_id(contact["personality_id"])

    return {
        "success": True,
        "data": {
            "contact": contact,
            "memory": memory,
            "personality": personality,
        },
    }


@router.patch("/{contact_id}")
async def update_contact(
    contact_id: str,
    body: dict[str, Any],
    _: CurrentUser,
) -> dict[str, Any]:
    """Update contact settings (AI enabled, personality, mode, etc.)."""
    db = get_database()
    repo = ContactRepository(db)
    contact = await repo.find_by_id(contact_id)
    if not contact:
        raise ContactNotFoundException()

    # Only allow safe fields to be updated
    allowed_fields = {
        "name", "nickname", "relationship", "personality_id",
        "ai_enabled", "auto_reply_mode", "voice_reply_enabled",
        "preferred_language", "is_blocked", "notes", "tags",
    }
    update_data = {k: v for k, v in body.items() if k in allowed_fields}
    await repo.update_one(contact_id, update_data)

    return {"success": True, "message": "Contact updated"}


@router.delete("/{contact_id}")
async def delete_contact(contact_id: str, _: CurrentUser) -> dict[str, Any]:
    """Soft-delete a contact (marks as inactive)."""
    db = get_database()
    repo = ContactRepository(db)
    await repo.update_one(contact_id, {"is_active": False})
    return {"success": True, "message": "Contact deactivated"}


@router.patch("/{contact_id}/ai-toggle")
async def toggle_ai_for_contact(
    contact_id: str,
    _: CurrentUser,
) -> dict[str, Any]:
    """
    Toggle AI auto-reply ON or OFF for a specific contact.
    Called from the Dashboard toggle switch — no body needed.
    Flips the current ai_enabled state and returns the new state.
    """
    db = get_database()
    repo = ContactRepository(db)
    contact = await repo.find_by_id(contact_id)
    if not contact:
        raise ContactNotFoundException()

    current_state = contact.get("ai_enabled", True)
    new_state = not current_state
    await repo.update_one(contact_id, {"ai_enabled": new_state})

    return {
        "success": True,
        "contact_id": contact_id,
        "ai_enabled": new_state,
        "message": f"AI {'enabled ✅' if new_state else 'disabled ❌'} for {contact.get('name', contact_id)}",
    }


@router.patch("/{contact_id}/mode")
async def set_contact_mode(
    contact_id: str,
    body: dict[str, Any],
    _: CurrentUser,
) -> dict[str, Any]:
    """
    Set auto_reply_mode for a contact: 'ai' or 'human'.
    'ai'    → AI replies automatically
    'human' → AI silent, you reply manually
    """
    db = get_database()
    repo = ContactRepository(db)
    contact = await repo.find_by_id(contact_id)
    if not contact:
        raise ContactNotFoundException()

    mode = body.get("mode", "ai")
    if mode not in ("ai", "human"):
        return {"success": False, "message": "mode must be 'ai' or 'human'"}

    await repo.update_one(contact_id, {"auto_reply_mode": mode})
    return {
        "success": True,
        "contact_id": contact_id,
        "auto_reply_mode": mode,
        "message": f"Mode set to {mode.upper()}",
    }


@router.patch("/{contact_id}/memory")

async def update_memory(
    contact_id: str,
    body: dict[str, Any],
    _: CurrentUser,
) -> dict[str, Any]:
    """Admin: directly edit contact AI memory fields."""
    db = get_database()
    memory_repo = MemoryRepository(db)
    allowed_fields = {
        "name", "nickname", "relationship", "birthday", "favourite_things",
        "personal_notes", "admin_notes", "preferred_language", "profession", "location",
    }
    update_data = {k: v for k, v in body.items() if k in allowed_fields}
    await memory_repo.upsert_memory(contact_id, update_data)
    return {"success": True, "message": "Memory updated"}


@router.post("/{contact_id}/broadcast")
async def send_broadcast(
    contact_id: str,
    body: dict[str, Any],
    _: CurrentUser,
) -> dict[str, Any]:
    """Send a manual message to a specific contact from the dashboard."""
    from app.whatsapp.client import get_whatsapp_client
    from app.repositories.message_repo import MessageRepository

    db = get_database()
    repo = ContactRepository(db)
    contact = await repo.find_by_id(contact_id)
    if not contact:
        raise ContactNotFoundException()

    text = body.get("message", "").strip()
    if not text:
        raise ValueError("Message cannot be empty")

    wa_client = get_whatsapp_client()
    result = await wa_client.send_text_message(contact["phone_number"], text)

    # Save to messages
    msg_repo = MessageRepository(db)
    await msg_repo.insert_one({
        "contact_id": contact_id,
        "direction": "outbound",
        "message_type": "text",
        "content": text,
        "status": "sent",
        "wa_message_id": result.get("messages", [{}])[0].get("id"),
    })

    return {"success": True, "message": "Message sent"}
