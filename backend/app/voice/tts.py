"""
Text-to-Speech Service
Converts AI-generated text to natural-sounding audio using Edge TTS (Microsoft).
Supports English (US), Urdu (PK), and Roman Urdu voices. 
Edge TTS is completely free with no API key required.
"""

import os
import tempfile
from pathlib import Path

import structlog

from app.core.config import settings
from app.core.exceptions import VoiceProcessingException

logger = structlog.get_logger(__name__)

# Voice mapping per language
VOICE_MAP: dict[str, str] = {
    "en": settings.DEFAULT_VOICE_EN,          # e.g., en-US-JennyNeural
    "ur": settings.DEFAULT_VOICE_UR,          # e.g., ur-PK-AsadNeural
    "roman_urdu": settings.DEFAULT_VOICE_UR,  # Use Urdu voice for Roman Urdu text
    "auto": settings.DEFAULT_VOICE_EN,        # Default to English
}


class TextToSpeechService:
    """
    Service for converting text to speech audio files.
    Uses Microsoft Edge TTS (via edge-tts library) — completely free,
    no API key needed, supports 400+ voices in 100+ languages.
    """

    async def synthesize(
        self,
        text: str,
        language: str = "en",
        output_format: str = "ogg",
    ) -> str | None:
        """
        Convert text to speech and save to a temporary audio file.

        Args:
            text: Text to synthesize.
            language: Language code ("en", "ur", "roman_urdu", "auto").
            output_format: Output format ("ogg" for WhatsApp compatibility).

        Returns:
            Path to the generated audio file, or None on failure.
        """
        if not text or not text.strip():
            return None

        # Limit text length (WhatsApp voice notes should be concise)
        text = text[:500] if len(text) > 500 else text

        try:
            return await self._synthesize_with_edge_tts(text, language)
        except Exception as e:
            logger.error("TTS synthesis failed", language=language, error=str(e))
            return None

    async def _synthesize_with_edge_tts(
        self,
        text: str,
        language: str,
    ) -> str | None:
        """
        Synthesize speech using edge-tts (Microsoft Neural TTS, free).
        Returns path to the generated OGG/OPUS file for WhatsApp.
        """
        try:
            import edge_tts

            voice = VOICE_MAP.get(language, settings.DEFAULT_VOICE_EN)

            # Create temp file for the audio output
            with tempfile.NamedTemporaryFile(
                suffix=".mp3", delete=False, dir=settings.MEDIA_UPLOAD_DIR
            ) as tmp:
                mp3_path = tmp.name

            # Generate speech
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(mp3_path)

            # Convert to OGG/OPUS for WhatsApp compatibility
            ogg_path = mp3_path.replace(".mp3", ".ogg")
            await self._convert_to_ogg(mp3_path, ogg_path)

            # Clean up MP3
            try:
                os.unlink(mp3_path)
            except OSError:
                pass

            if Path(ogg_path).exists() and Path(ogg_path).stat().st_size > 0:
                logger.info(
                    "TTS synthesis complete",
                    voice=voice,
                    language=language,
                    file=ogg_path,
                )
                return ogg_path

            return None

        except ImportError:
            logger.error("edge-tts not installed. Run: pip install edge-tts")
            return None
        except Exception as e:
            logger.error("Edge TTS failed", error=str(e))
            return None

    @staticmethod
    async def _convert_to_ogg(input_path: str, output_path: str) -> None:
        """
        Convert audio to OGG/OPUS format using pydub + ffmpeg.
        WhatsApp requires OGG/OPUS for voice messages.
        """
        import asyncio
        import subprocess

        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-c:a", "libopus",
            "-b:a", "32k",
            "-y",  # Overwrite output
            output_path,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except FileNotFoundError:
            # ffmpeg not available — try pydub as fallback
            from pydub import AudioSegment
            audio = AudioSegment.from_mp3(input_path)
            audio.export(output_path, format="ogg", codec="libopus")
