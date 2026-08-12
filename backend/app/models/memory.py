"""
ConversationMemory MongoDB Document Model
Stores AI-maintained memory for each contact.
Auto-updated after every conversation by the memory service.
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.base import MongoBaseModel


class ImportantDate(MongoBaseModel):
    """Structured important date entry."""
    label: str  # e.g., "birthday", "anniversary", "promotion_date"
    date: str  # ISO date string or partial (e.g., "1990-05-15" or "May 15")
    notes: str | None = None


class MemoryModel(MongoBaseModel):
    """
    AI memory document in the 'conversation_memory' collection.
    One document per contact. Contains everything the AI remembers
    about this person to provide personalized, context-aware responses.
    """

    # Reference
    contact_id: str  # Unique reference to contacts collection

    # --- Profile Information (auto-extracted by AI) ---
    name: str | None = None
    nickname: str | None = None
    relationship: str | None = None  # family | friend | colleague | client | romantic
    profession: str | None = None
    location: str | None = None
    age: int | None = None

    # --- Important Dates ---
    birthday: str | None = None  # "YYYY-MM-DD" or "MM-DD"
    important_dates: list[dict[str, str]] = Field(default_factory=list)
    # e.g., [{"label": "anniversary", "date": "2020-06-01"}]

    # --- Preferences ---
    favourite_things: list[str] = Field(default_factory=list)
    # e.g., ["cricket", "biryani", "Urdu poetry"]

    disliked_things: list[str] = Field(default_factory=list)

    # --- Conversation Style ---
    preferred_language: str = "en"  # en | ur | roman_urdu | auto
    emoji_usage: str = "moderate"  # none | minimal | moderate | heavy
    reply_length: str = "medium"  # short | medium | long
    conversation_tone: str = "friendly"  # formal | casual | funny | friendly | professional

    # --- Context Memory (for conversation continuity) ---
    last_topic: str | None = None
    last_topic_summary: str | None = None
    ongoing_context: str | None = None  # Brief summary of active conversation thread
    pending_questions: list[str] = Field(default_factory=list)  # Unanswered questions

    # --- Personal Notes (admin-editable) ---
    personal_notes: str | None = None
    admin_notes: str | None = None

    # --- Conversation History Summary ---
    # AI-generated summary of overall relationship and past interactions
    relationship_summary: str | None = None
    total_conversations: int = 0
    last_conversation_at: datetime | None = None

    # --- Raw facts extracted by AI (flexible key-value store) ---
    extracted_facts: dict[str, Any] = Field(default_factory=dict)
    # e.g., {"owns_business": true, "business_name": "XYZ", "lives_in": "Karachi"}

    # Memory health
    last_memory_update: datetime | None = None
    memory_version: int = 1  # Incremented on each AI update
