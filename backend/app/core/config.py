"""
Application Configuration — Pydantic Settings v2
All settings loaded from environment variables with full validation.
"""

import json
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration class. All values are loaded from .env file
    or environment variables. Provides type safety and validation.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application ----
    APP_NAME: str = "AI WhatsApp Assistant"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    SECRET_KEY: str = "this-is-a-super-secret-key-for-whatsapp-ai-assistant-app"
    ALLOWED_HOSTS: list[str] = ["*"]
    FRONTEND_URL: str = "http://localhost:8000"

    # ---- MongoDB ----
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "whatsapp_ai"

    # ---- Redis (optional — disabled by default) ----
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str = ""

    # ---- JWT ----
    JWT_SECRET_KEY: str = "this-is-a-jwt-secret-key-for-whatsapp-ai-assistant-2024"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ---- Admin (default credentials — change in production!) ----
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "Admin@12345"
    ADMIN_NAME: str = "Admin"

    # ---- WhatsApp (optional — configure when connecting to Meta API) ----
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "my_verify_token"
    WHATSAPP_API_VERSION: str = "v21.0"
    WHATSAPP_API_BASE_URL: str = "https://graph.facebook.com"

    # ---- AI Providers (configure at least one) ----
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"
    GEMINI_MAX_TOKENS: int = 2048
    GEMINI_TEMPERATURE: float = 0.7

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "anthropic/claude-3-haiku"

    TOGETHER_API_KEY: str = ""
    TOGETHER_MODEL: str = "meta-llama/Llama-3-70b-chat-hf"

    REPLICATE_API_TOKEN: str = ""

    ACTIVE_AI_PROVIDER: str = "gemini"
    AUTO_FALLBACK_ENABLED: bool = True

    # ---- Voice ----
    VOICE_ENGINE: str = "edge_tts"
    DEFAULT_VOICE_EN: str = "en-US-JennyNeural"
    DEFAULT_VOICE_UR: str = "ur-PK-AsadNeural"
    WHISPER_MODEL: str = "whisper-large-v3"

    # ---- Web Search ----
    SEARCH_ENGINE: str = "duckduckgo"
    MAX_SEARCH_RESULTS: int = 5
    WEATHER_API_URL: str = "https://api.open-meteo.com/v1/forecast"
    GEOCODING_API_URL: str = "https://geocoding-api.open-meteo.com/v1/search"
    NEWS_API_KEY: str = ""
    NEWS_API_URL: str = "https://newsdata.io/api/1/news"

    # ---- Rate Limiting ----
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000

    # ---- Logging ----
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "console"

    # ---- Celery (optional) ----
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ---- CORS ----
    CORS_ORIGINS: list[str] = ["*"]

    # ---- File Storage ----
    MEDIA_UPLOAD_DIR: str = "C:/tmp/whatsapp_media"
    MAX_VOICE_SIZE_MB: int = 10

    @field_validator("ALLOWED_HOSTS", "CORS_ORIGINS", mode="before")
    @classmethod
    def parse_json_or_comma_list(cls, v: "str | list") -> "list[str]":
        """Parse JSON arrays or comma-separated strings into lists."""
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @property
    def whatsapp_configured(self) -> bool:
        """Check if WhatsApp credentials are configured."""
        return bool(self.WHATSAPP_PHONE_NUMBER_ID and self.WHATSAPP_ACCESS_TOKEN)

    @property
    def whatsapp_api_url(self) -> str:
        """Construct full WhatsApp API URL."""
        return f"{self.WHATSAPP_API_BASE_URL}/{self.WHATSAPP_API_VERSION}"

    @property
    def whatsapp_messages_url(self) -> str:
        """Construct WhatsApp messages endpoint URL."""
        return f"{self.whatsapp_api_url}/{self.WHATSAPP_PHONE_NUMBER_ID}/messages"

    @property
    def whatsapp_headers(self) -> "dict[str, str]":
        """WhatsApp API authentication headers."""
        return {
            "Authorization": f"Bearer {self.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }


# Singleton settings instance
settings = Settings()  # type: ignore[call-arg]
