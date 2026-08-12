"""
AI Service — Multi-Provider Abstraction Layer
Implements the Strategy pattern for AI provider selection with automatic fallback.
All providers implement the AIProvider abstract interface.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any

import structlog

from app.core.config import settings
from app.core.exceptions import AIProviderException, AIQuotaExceededException

logger = structlog.get_logger(__name__)


# ============================================================
# Abstract Base Provider
# ============================================================

class AIProvider(ABC):
    """
    Abstract interface that all AI provider implementations must follow.
    Ensures consistent behavior regardless of which provider is active.
    """

    provider_name: str = "base"

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """
        Generate an AI response.

        Args:
            messages: List of {"role": "user/assistant", "content": str} dicts.
            system_prompt: System-level instructions for the AI.
            temperature: Creativity level (0.0-2.0).
            max_tokens: Maximum tokens in the response.

        Returns:
            Generated text response.

        Raises:
            AIQuotaExceededException: When provider quota is exhausted.
            AIProviderException: On other provider failures.
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if this provider is configured and reachable."""
        ...


# ============================================================
# AI Service — Provider Orchestrator
# ============================================================

class AIService:
    """
    Orchestrates AI provider selection and automatic fallback.

    On each generation request:
    1. Tries the configured active provider first.
    2. On quota exhaustion or error, automatically switches to the next
       provider in the fallback_order list.
    3. Logs all provider switches for audit trail.
    """

    def __init__(self, providers: dict[str, AIProvider]) -> None:
        """
        Args:
            providers: Dict mapping provider name -> AIProvider instance.
        """
        self._providers = providers
        self._current_provider_name = settings.ACTIVE_AI_PROVIDER
        self._fallback_order = self._build_fallback_order()

    def _build_fallback_order(self) -> list[str]:
        """Build provider priority list starting from the active provider."""
        default_order = ["gemini", "groq", "openai", "openrouter", "together"]
        # Put active provider first
        order = [self._current_provider_name]
        for p in default_order:
            if p not in order and p in self._providers:
                order.append(p)
        return order

    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> tuple[str, str]:
        """
        Generate an AI response, with automatic provider fallback.

        Returns:
            Tuple of (response_text, provider_name_used)

        Raises:
            AIProviderException: When all providers fail.
        """
        temp = temperature or settings.GEMINI_TEMPERATURE
        tokens = max_tokens or settings.GEMINI_MAX_TOKENS

        last_error: Exception | None = None

        for provider_name in self._fallback_order:
            provider = self._providers.get(provider_name)
            if not provider:
                continue

            if not await provider.is_available():
                logger.warning("AI provider not available, skipping", provider=provider_name)
                continue

            try:
                start_time = time.perf_counter()
                response = await provider.generate(
                    messages=messages,
                    system_prompt=system_prompt,
                    temperature=temp,
                    max_tokens=tokens,
                    **kwargs,
                )
                duration_ms = int((time.perf_counter() - start_time) * 1000)

                if provider_name != self._current_provider_name:
                    logger.info(
                        "AI fallback provider used",
                        primary=self._current_provider_name,
                        used=provider_name,
                    )
                else:
                    logger.debug("AI response generated", provider=provider_name, duration_ms=duration_ms)

                return response, provider_name

            except AIQuotaExceededException:
                logger.warning(
                    "AI provider quota exceeded, trying next",
                    provider=provider_name,
                )
                last_error = AIQuotaExceededException()
                continue

            except Exception as e:
                logger.error(
                    "AI provider error, trying next",
                    provider=provider_name,
                    error=str(e),
                )
                last_error = e
                continue

        raise AIProviderException(
            detail=f"All AI providers failed. Last error: {last_error}"
        )

    def set_active_provider(self, provider_name: str) -> None:
        """Switch the active provider at runtime (from dashboard)."""
        if provider_name not in self._providers:
            raise ValueError(f"Unknown provider: {provider_name}")
        self._current_provider_name = provider_name
        self._fallback_order = self._build_fallback_order()
        logger.info("AI provider switched", provider=provider_name)

    def get_active_provider_name(self) -> str:
        """Return the name of the currently active provider."""
        return self._current_provider_name

    def get_available_providers(self) -> list[str]:
        """Return list of configured provider names."""
        return list(self._providers.keys())


# ============================================================
# Provider Factory — creates the AIService singleton
# ============================================================

def create_ai_service() -> AIService:
    """
    Factory function that instantiates all configured AI providers
    and returns a ready-to-use AIService instance.
    """
    from app.services.providers.gemini_provider import GeminiProvider
    from app.services.providers.groq_provider import GroqProvider
    from app.services.providers.openai_provider import OpenAIProvider
    from app.services.providers.openrouter_provider import OpenRouterProvider
    from app.services.providers.together_provider import TogetherProvider

    providers: dict[str, AIProvider] = {}

    if settings.GEMINI_API_KEY:
        providers["gemini"] = GeminiProvider()

    if settings.OPENAI_API_KEY:
        providers["openai"] = OpenAIProvider()

    if settings.GROQ_API_KEY:
        providers["groq"] = GroqProvider()

    if settings.OPENROUTER_API_KEY:
        providers["openrouter"] = OpenRouterProvider()

    if settings.TOGETHER_API_KEY:
        providers["together"] = TogetherProvider()

    if not providers:
        raise RuntimeError(
            "No AI providers configured. Set at least one API key in .env"
        )

    logger.info("AI service initialized", providers=list(providers.keys()))
    return AIService(providers)


# Module-level singleton
_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    """Get or create the AI service singleton."""
    global _ai_service
    if _ai_service is None:
        _ai_service = create_ai_service()
    return _ai_service
