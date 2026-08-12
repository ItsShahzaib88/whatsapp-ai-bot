"""
AI Settings MongoDB Document Model
Stores AI provider configuration and behavior settings.
"""

from pydantic import Field

from app.models.base import MongoBaseModel


class AISettingsModel(MongoBaseModel):
    """
    AI settings document in the 'ai_settings' collection.
    Controls which AI provider is active, model parameters,
    and fallback behavior. Configurable from dashboard.
    """

    # Active provider
    active_provider: str = "gemini"
    # Options: gemini | openai | groq | openrouter | together

    # Provider fallback order (tried in order on quota/error)
    fallback_order: list[str] = Field(
        default_factory=lambda: ["gemini", "groq", "openai", "openrouter", "together"]
    )
    auto_fallback_enabled: bool = True

    # Model configuration per provider
    gemini_model: str = "gemini-2.0-flash-exp"
    openai_model: str = "gpt-4o-mini"
    groq_model: str = "llama-3.3-70b-versatile"
    openrouter_model: str = "anthropic/claude-3-haiku"
    together_model: str = "meta-llama/Llama-3-70b-chat-hf"

    # Generation parameters
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=100, le=8192)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)

    # Context window (number of past messages to include)
    context_window_size: int = Field(default=10, ge=1, le=50)

    # Memory settings
    auto_update_memory: bool = True
    memory_update_frequency: int = 1  # Update memory every N messages

    # Web search settings
    web_search_enabled: bool = True
    auto_detect_search_intent: bool = True
    max_search_results: int = 3

    # Voice settings
    voice_reply_enabled: bool = False
    tts_engine: str = "edge_tts"
    stt_engine: str = "groq_whisper"

    # System-level
    ai_enabled_globally: bool = True
    max_response_time_seconds: int = 30

    # Current provider stats (updated at runtime)
    gemini_requests_today: int = 0
    groq_requests_today: int = 0
    openai_requests_today: int = 0
