from typing import Any
import structlog
from app.core.config import settings
from app.core.exceptions import AIProviderException, AIQuotaExceededException
from app.services.ai_service import AIProvider

logger = structlog.get_logger(__name__)


class GroqProvider(AIProvider):
    """Groq AI provider - fast LPU inference, free tier 14400 req/day."""

    provider_name = "groq"

    def __init__(self) -> None:
        self._model = settings.GROQ_MODEL
        self._client = None

    def _get_client(self):
        if self._client is None:
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        return self._client

    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        try:
            client = self._get_client()
            full_messages = []
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            full_messages.extend(messages)
            response = await client.chat.completions.create(
                model=self._model,
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.9,
            )
            content = response.choices[0].message.content
            if not content:
                raise AIProviderException(detail="Groq returned empty response")
            return content.strip()
        except AIProviderException:
            raise
        except Exception as e:
            err = str(e).lower()
            if "rate_limit" in err or "quota" in err or "429" in err:
                logger.warning("Groq rate limit hit", error=str(e))
                raise AIQuotaExceededException()
            logger.error("Groq generation failed", model=self._model, error=str(e))
            raise AIProviderException(detail=f"Groq error: {str(e)}")

    async def is_available(self) -> bool:
        return bool(settings.GROQ_API_KEY)
