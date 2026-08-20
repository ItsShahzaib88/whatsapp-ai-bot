"""
WhatsApp Internal Webhook Router
Handles messages coming from our local Node.js WhatsApp Web bridge.
This is the UNOFFICIAL bot path — no Meta Cloud API involved.
"""

from typing import Any
import structlog
from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks

from app.services.whatsapp_service import WhatsAppService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/internal")


class IncomingMessage(BaseModel):
    phone: str
    text: str = ""
    name: str = "User"
    media_data: str | None = None
    media_mimetype: str | None = None


@router.post("/message")
async def receive_internal_message(
    msg: IncomingMessage,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """
    Receives a message from the Node.js WhatsApp Web bridge and processes it.
    
    Returns:
        { "reply": "<ai reply text>" }  — bridge will send this back to WhatsApp
        { "reply": null }               — bridge will silently skip (AI disabled for contact)
    """
    logger.info(f"Bridge message from {msg.phone}: {msg.text[:80]}")

    service = WhatsAppService()

    try:
        reply = await service.process_internal_message(
            phone=msg.phone,
            text=msg.text,
            name=msg.name,
            media_data=msg.media_data,
            media_mimetype=msg.media_mimetype,
        )
        
        # Check if the service returned a dict with media (for image generation)
        if isinstance(reply, dict):
            return {"reply": reply.get("reply"), "media_url": reply.get("media_url")}

        # reply is None when AI is toggled off for this contact
        return {"reply": reply}

    except Exception as e:
        logger.error("Failed to process bridge message", error=str(e), phone=msg.phone)
        return {"reply": "Sorry, I encountered an internal error. Please try again."}
