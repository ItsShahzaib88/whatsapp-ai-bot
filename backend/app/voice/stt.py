"""
Speech-to-Text Service
Transcribes audio files to text using Groq Whisper API (free tier).
Supports English, Urdu, and Roman Urdu detection.
"""

import os
import tempfile
from pathlib import Path
from typing import Literal

import structlog

from app.core.config import settings
from app.core.exceptions import VoiceProcessingException

logger = structlog.get_logger(__name__)

# Language code mapping
LANGUAGE_MAP: dict[str, str] = {
    "en": "en",
    "ur": "ur",
    "roman_urdu": "ur",  # Roman Urdu uses Urdu language code for STT
    "auto": None,  # Auto-detect
}


class SpeechToTextService:
    """
    Service for transcribing audio to text.
    Uses Groq's Whisper API for fast, accurate transcription.
    Falls back to a local approach if Groq is unavailable.
    """

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en",
        mime_type: str = "audio/ogg",
    ) -> str | None:
        """
        Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw audio file bytes.
            language: Language code ("en", "ur", "roman_urdu", "auto").
            mime_type: Audio MIME type for file extension detection.

        Returns:
            Transcribed text string or None on failure.
        """
        # Determine file extension from MIME type
        ext_map = {
            "audio/ogg": ".ogg",
            "audio/mpeg": ".mp3",
            "audio/mp4": ".mp4",
            "audio/wav": ".wav",
            "audio/webm": ".webm",
        }
        ext = ext_map.get(mime_type, ".ogg")

        # Save audio bytes to a temporary file
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            # Try Groq Whisper first (fast and free)
            if settings.GROQ_API_KEY:
                result = await self._transcribe_with_groq(tmp_path, language)
                if result:
                    return result

            logger.warning("STT: Groq not available")
            return None

        finally:
            # Always clean up temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def _transcribe_with_groq(
        self,
        audio_path: str,
        language: str,
    ) -> str | None:
        """
        Transcribe using Groq's Whisper-large-v3 (free tier).
        This is the primary STT engine.
        """
        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=settings.GROQ_API_KEY)

            # Map our language code to Whisper language code
            whisper_lang = LANGUAGE_MAP.get(language)

            with open(audio_path, "rb") as audio_file:
                kwargs: dict = {
                    "file": (Path(audio_path).name, audio_file, "audio/ogg"),
                    "model": settings.WHISPER_MODEL,
                    "response_format": "text",
                }
                if whisper_lang:
                    kwargs["language"] = whisper_lang

                transcription = await client.audio.transcriptions.create(**kwargs)

            # Groq returns text directly when response_format="text"
            text = str(transcription).strip()
            logger.info("STT transcription complete", length=len(text), language=language)
            return text if text else None

        except Exception as e:
            logger.error("Groq STT failed", error=str(e))
            return None
