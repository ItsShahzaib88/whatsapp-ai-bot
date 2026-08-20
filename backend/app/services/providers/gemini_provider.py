"""
Google Gemini AI Provider Implementation
Uses the google-generativeai SDK with async support.
"""

from typing import Any

import structlog
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from app.core.config import settings
from app.core.exceptions import AIProviderException, AIQuotaExceededException
from app.services.ai_service import AIProvider

logger = structlog.get_logger(__name__)


class GeminiProvider(AIProvider):
    """
    Google Gemini AI provider.
    Primary provider with support for Gemini 2.0 Flash (free tier).
    """

    provider_name = "gemini"

    def __init__(self) -> None:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._model_name = settings.GEMINI_MODEL
        self._model: genai.GenerativeModel | None = None

    def _get_model(self, system_prompt: str) -> genai.GenerativeModel:
        """Get or create the Gemini model with system instructions."""
        return genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system_prompt if system_prompt else None,
        )

    async def generate(
        self,
        messages: list[dict[str, str]],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> str:
        """
        Generate a response using Google Gemini.
        Converts OpenAI-style messages to Gemini's content format.
        """
        try:
            model = self._get_model(system_prompt)

            # Convert messages to Gemini format
            gemini_history = []
            last_user_message = ""

            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                
                parts = []
                if msg.get("content"):
                    parts.append(msg["content"])
                    
                if msg.get("media_data") and msg.get("media_mimetype"):
                    parts.append({
                        "mime_type": msg["media_mimetype"],
                        "data": msg["media_data"]
                    })
                
                if not parts:
                    parts.append(" ") # fallback empty message

                if msg == messages[-1] and msg["role"] == "user":
                    last_user_message = parts
                else:
                    gemini_history.append({
                        "role": role,
                        "parts": parts,
                    })

            # Start chat with history
            chat = model.start_chat(history=gemini_history)

            # Generate response
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                top_p=0.9,
            )

            response = await chat.send_message_async(
                last_user_message or (messages[-1]["content"] if messages else "Hello"),
                generation_config=generation_config,
            )

            return response.text

        except ResourceExhausted as e:
            logger.warning("Gemini quota exhausted", error=str(e))
            raise AIQuotaExceededException()

        except Exception as e:
            logger.error("Gemini generation failed", error=str(e))
            raise AIProviderException(detail=f"Gemini error: {str(e)}")

    async def is_available(self) -> bool:
        """Check if Gemini API key is configured."""
        return bool(settings.GEMINI_API_KEY)
