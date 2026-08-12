"""
OpenAI Provider Implementation
Supports GPT-4o Mini and other OpenAI models via async client.
"""

from typing import Any

import structlog
from openai import AsyncOpenAI, RateLimitError

from app.core.config import settings
from app.core.exceptions import AIProviderException, AIQuotaExceededException
from app.services.ai_service import AIProvider

logger = structlog.get_logger(__name__)


class OpenAIProvider(AIProvider):
    """
    OpenAI provider using the official async Python client.
    Fallback 1 when Gemini quota is exhausted.
    """

    provider_name = "openai"

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self._model = settings.OPENAI_MODEL

    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """Generate a response using OpenAI Chat Completions API."""
        try:
            # Build messages with system prompt
            full_messages: list[dict[str, str]] = []
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            full_messages.extend(messages)

            response = await self._client.chat.completions.create(
                model=self._model,
                messages=full_messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )

            return response.choices[0].message.content or ""

        except RateLimitError as e:
            logger.warning("OpenAI rate limit hit", error=str(e))
            raise AIQuotaExceededException()

        except Exception as e:
            logger.error("OpenAI generation failed", error=str(e))
            raise AIProviderException(detail=f"OpenAI error: {str(e)}")

    async def is_available(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(settings.OPENAI_API_KEY)


class GroqProvider(AIProvider):
    """
    Groq AI provider — fast inference with free tier.
    Supports Llama 3.3 70B and other open-source models.
    Fallback 2 when both Gemini and OpenAI fail.
    """

    provider_name = "groq"

    def __init__(self) -> None:
        from groq import AsyncGroq
        self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self._model = settings.GROQ_MODEL

    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """Generate a response using Groq's ultra-fast inference API."""
        try:
            full_messages: list[dict[str, str]] = []
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            full_messages.extend(messages)

            response = await self._client.chat.completions.create(
                model=self._model,
                messages=full_messages,  # type: ignore[arg-type]
                temperature=min(temperature, 1.0),  # Groq caps at 1.0
                max_tokens=max_tokens,
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            error_str = str(e).lower()
            if "rate limit" in error_str or "quota" in error_str:
                raise AIQuotaExceededException()
            logger.error("Groq generation failed", error=str(e))
            raise AIProviderException(detail=f"Groq error: {str(e)}")

    async def is_available(self) -> bool:
        """Check if Groq API key is configured."""
        return bool(settings.GROQ_API_KEY)


class OpenRouterProvider(AIProvider):
    """
    OpenRouter provider — aggregates multiple AI models.
    Uses OpenAI-compatible API endpoint.
    Fallback 3.
    """

    provider_name = "openrouter"

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        )
        self._model = settings.OPENROUTER_MODEL

    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """Generate a response using OpenRouter's aggregated model API."""
        try:
            full_messages: list[dict[str, str]] = []
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            full_messages.extend(messages)

            response = await self._client.chat.completions.create(
                model=self._model,
                messages=full_messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                extra_headers={
                    "HTTP-Referer": "https://whatsapp-ai-assistant.app",
                    "X-Title": "AI WhatsApp Assistant",
                },
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            error_str = str(e).lower()
            if "rate limit" in error_str or "quota" in error_str:
                raise AIQuotaExceededException()
            logger.error("OpenRouter generation failed", error=str(e))
            raise AIProviderException(detail=f"OpenRouter error: {str(e)}")

    async def is_available(self) -> bool:
        return bool(settings.OPENROUTER_API_KEY)


class TogetherProvider(AIProvider):
    """
    Together AI provider — open-source model hosting.
    Uses OpenAI-compatible endpoint.
    Fallback 4 (last resort).
    """

    provider_name = "together"

    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.TOGETHER_API_KEY,
            base_url="https://api.together.xyz/v1",
        )
        self._model = settings.TOGETHER_MODEL

    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """Generate a response using Together AI."""
        try:
            full_messages: list[dict[str, str]] = []
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            full_messages.extend(messages)

            response = await self._client.chat.completions.create(
                model=self._model,
                messages=full_messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            error_str = str(e).lower()
            if "rate limit" in error_str or "quota" in error_str:
                raise AIQuotaExceededException()
            logger.error("Together AI generation failed", error=str(e))
            raise AIProviderException(detail=f"Together AI error: {str(e)}")

    async def is_available(self) -> bool:
        return bool(settings.TOGETHER_API_KEY)
