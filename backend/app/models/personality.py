"""
Personality MongoDB Document Model
Defines AI personality templates that can be assigned to contacts.
"""

from pydantic import Field

from app.models.base import MongoBaseModel


class PersonalityModel(MongoBaseModel):
    """
    Personality template document in the 'personalities' collection.
    Each personality defines how the AI should behave with a specific contact.
    Admin can create, edit and assign personalities from the dashboard.
    """

    name: str = Field(min_length=1, max_length=100)
    display_name: str
    description: str = ""

    # Personality category
    category: str = "custom"
    # Options: family | friends | office | romantic | professional | custom

    # Core personality traits
    tone: str = "friendly"
    # Options: friendly | casual | professional | formal | funny | loving | caring | respectful

    # Communication style
    emoji_usage: str = "moderate"
    # Options: none | minimal | moderate | heavy

    reply_length: str = "medium"
    # Options: short | medium | long | adaptive

    language_style: str = "balanced"
    # Options: formal | casual | mixed | balanced

    # AI Persona instructions (injected into system prompt)
    persona_instructions: str = ""
    # e.g., "You are a caring family member. Always ask about health and family."

    # Forbidden topics / behaviors
    avoid_topics: list[str] = Field(default_factory=list)
    # e.g., ["politics", "religion"]

    # Greeting style
    greeting_style: str | None = None
    # e.g., "Start replies with 'Assalam o Alaikum'"

    # Sign-off style
    signoff_style: str | None = None
    # e.g., "End with a warm closing"

    # Language preference
    preferred_language: str = "auto"  # auto | en | ur | roman_urdu

    # Status
    is_default: bool = False
    is_active: bool = True

    # Usage stats
    assigned_contacts: int = 0
