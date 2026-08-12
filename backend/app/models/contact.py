"""
Contact MongoDB Document Model
Represents WhatsApp contacts with personality and AI memory configuration.
"""

from pydantic import Field

from app.models.base import MongoBaseModel


class ContactModel(MongoBaseModel):
    """
    Contact document in the 'contacts' collection.
    Each contact has a unique phone number, associated personality,
    and references to their AI memory document.
    """

    # Identity
    phone_number: str = Field(description="WhatsApp phone number in E.164 format")
    name: str = Field(default="Unknown", max_length=100)
    nickname: str | None = None
    profile_picture_url: str | None = None

    # WhatsApp Profile (auto-populated from API)
    wa_name: str | None = None  # Name from WhatsApp profile

    # Relationship & Personality
    relationship: str = "unknown"  # family | friend | colleague | client | romantic | unknown
    personality_id: str | None = None  # Reference to personalities collection
    custom_personality_override: str | None = None  # Inline personality override

    # Status
    is_active: bool = True
    is_blocked: bool = False
    ai_enabled: bool = True  # Master toggle for AI replies

    # Auto Reply Mode
    auto_reply_mode: str = "ai"  # "ai" | "human" | "off"

    # Voice preferences
    voice_reply_enabled: bool = False
    preferred_language: str = "en"  # en | ur | roman_urdu

    # Statistics
    total_messages_sent: int = 0
    total_messages_received: int = 0
    last_message_at: str | None = None  # ISO timestamp string

    # Tags for filtering
    tags: list[str] = Field(default_factory=list)

    # Notes
    notes: str | None = None
