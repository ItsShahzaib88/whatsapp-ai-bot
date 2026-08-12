"""
Message MongoDB Document Model
Stores all incoming and outgoing WhatsApp messages.
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.base import MongoBaseModel


class MessageModel(MongoBaseModel):
    """
    Message document in the 'messages' collection.
    Tracks every message exchanged with full metadata for analytics and history.
    """

    # References
    contact_id: str  # Reference to contacts collection
    conversation_id: str | None = None  # Logical conversation grouping

    # WhatsApp metadata
    wa_message_id: str | None = None  # WhatsApp's message ID (wamid)
    wa_timestamp: str | None = None  # WhatsApp's timestamp

    # Message content
    direction: str  # "inbound" | "outbound"
    message_type: str  # "text" | "voice" | "image" | "video" | "document" | "sticker"
    content: str = ""  # Text content or transcription for voice
    media_url: str | None = None  # URL for media messages
    media_id: str | None = None  # WhatsApp media ID

    # For voice messages
    voice_transcript: str | None = None  # STT result
    is_voice_reply: bool = False  # Whether reply was sent as voice

    # AI processing metadata
    ai_provider_used: str | None = None  # Which AI provider generated the reply
    ai_model_used: str | None = None
    tokens_used: int | None = None
    processing_time_ms: int | None = None

    # Delivery tracking
    status: str = "pending"  # pending | sent | delivered | read | failed
    status_updated_at: datetime | None = None
    failure_reason: str | None = None
    retry_count: int = 0
    max_retries: int = 3

    # Context
    is_command: bool = False  # Was this a /command message
    command_name: str | None = None
    requires_web_search: bool = False
    web_search_query: str | None = None

    # Raw webhook payload for debugging
    raw_payload: dict[str, Any] | None = None
