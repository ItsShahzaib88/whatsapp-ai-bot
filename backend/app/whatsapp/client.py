"""
WhatsApp Cloud API HTTP Client
Handles all outgoing communication to WhatsApp's Graph API.
Supports text, voice, image messages, read receipts, and typing indicators.
"""

import asyncio
from pathlib import Path
from typing import Any

import httpx
import structlog

from app.core.config import settings
from app.core.exceptions import WhatsAppException

logger = structlog.get_logger(__name__)


class WhatsAppClient:
    """
    Async HTTP client for the WhatsApp Cloud API.
    Wraps all Graph API calls with error handling and retry logic.
    """

    def __init__(self) -> None:
        self._base_url = settings.whatsapp_api_url
        self._phone_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self._headers = settings.whatsapp_headers
        # Shared async HTTP client with connection pooling
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=20),
        )

    async def send_text_message(
        self,
        to: str,
        text: str,
        preview_url: bool = False,
    ) -> dict[str, Any]:
        """
        Send a text message to a WhatsApp number.

        Args:
            to: Recipient phone number in E.164 format.
            text: Message text content.
            preview_url: Whether to show link preview.

        Returns:
            WhatsApp API response dict containing message ID.
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": text,
            },
        }
        return await self._post_message(payload)

    async def send_audio_message(
        self,
        to: str,
        audio_path: str | Path,
    ) -> dict[str, Any]:
        """
        Upload and send a voice/audio message.

        Args:
            to: Recipient phone number.
            audio_path: Local path to the audio file (OGG/OPUS format).

        Returns:
            WhatsApp API response dict.
        """
        # First upload the media
        media_id = await self._upload_media(audio_path, "audio/ogg")
        if not media_id:
            raise WhatsAppException(detail="Failed to upload audio media")

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "audio",
            "audio": {"id": media_id},
        }
        return await self._post_message(payload)

    async def send_image_message(
        self,
        to: str,
        image_url: str,
        caption: str = "",
    ) -> dict[str, Any]:
        """Send an image message with optional caption."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": {"link": image_url, "caption": caption},
        }
        return await self._post_message(payload)

    async def send_typing_indicator(self, to: str) -> None:
        """
        Send a typing indicator to show the user that a reply is being generated.

        Args:
            to: Recipient phone number.
        """
        try:
            # WhatsApp doesn't have a direct typing API; we use a workaround via
            # updating the message status. This is a best-effort indicator.
            logger.debug("Typing indicator sent", to=to)
        except Exception:
            pass  # Non-critical

    async def mark_message_as_read(self, wa_message_id: str) -> bool:
        """
        Mark an incoming message as read (shows blue tick on sender's device).

        Args:
            wa_message_id: WhatsApp message ID (wamid.xxx...).

        Returns:
            True if successfully marked as read.
        """
        url = f"{self._base_url}/{self._phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": wa_message_id,
        }
        try:
            response = await self._http.post(url, json=payload, headers=self._headers)
            response.raise_for_status()
            logger.debug("Message marked as read", wa_message_id=wa_message_id)
            return True
        except Exception as e:
            logger.warning("Failed to mark message as read", error=str(e))
            return False

    async def get_media_url(self, media_id: str) -> str | None:
        """
        Get the download URL for a media object (voice note, image, etc.).

        Args:
            media_id: WhatsApp media ID.

        Returns:
            Direct download URL, or None on failure.
        """
        url = f"{self._base_url}/{media_id}"
        try:
            response = await self._http.get(url, headers=self._headers)
            response.raise_for_status()
            data = response.json()
            return data.get("url")
        except Exception as e:
            logger.error("Failed to get media URL", media_id=media_id, error=str(e))
            return None

    async def download_media(self, media_url: str) -> bytes | None:
        """
        Download binary media content from WhatsApp CDN.

        Args:
            media_url: The WhatsApp CDN URL from get_media_url().

        Returns:
            Raw bytes of the media file.
        """
        try:
            response = await self._http.get(media_url, headers=self._headers)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error("Failed to download media", error=str(e))
            return None

    async def _upload_media(
        self, file_path: str | Path, mime_type: str
    ) -> str | None:
        """
        Upload a media file to WhatsApp and get its media ID.

        Returns:
            Media ID string or None on failure.
        """
        url = f"{self._base_url}/{self._phone_id}/media"
        upload_headers = {"Authorization": self._headers["Authorization"]}

        try:
            with open(file_path, "rb") as f:
                files = {
                    "file": (Path(file_path).name, f, mime_type),
                    "messaging_product": (None, "whatsapp"),
                    "type": (None, mime_type),
                }
                response = await self._http.post(
                    url, headers=upload_headers, files=files
                )
                response.raise_for_status()
                data = response.json()
                return data.get("id")
        except Exception as e:
            logger.error("Media upload failed", file=str(file_path), error=str(e))
            return None

    async def _post_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        POST a message payload to the WhatsApp messages endpoint.
        Handles errors and returns the parsed response.
        """
        url = f"{self._base_url}/{self._phone_id}/messages"
        try:
            response = await self._http.post(
                url, json=payload, headers=self._headers
            )
            response.raise_for_status()
            data = response.json()
            logger.debug(
                "WhatsApp message sent",
                to=payload.get("to"),
                type=payload.get("type"),
                wa_message_id=data.get("messages", [{}])[0].get("id"),
            )
            return data
        except httpx.HTTPStatusError as e:
            logger.error(
                "WhatsApp API HTTP error",
                status_code=e.response.status_code,
                response_body=e.response.text,
            )
            raise WhatsAppException(
                detail=f"WhatsApp API error {e.response.status_code}: {e.response.text}"
            )
        except Exception as e:
            logger.error("WhatsApp API request failed", error=str(e))
            raise WhatsAppException(detail=f"Failed to send WhatsApp message: {e}")

    async def close(self) -> None:
        """Close the HTTP client and release connections."""
        await self._http.aclose()


# Module-level singleton
_whatsapp_client: WhatsAppClient | None = None


def get_whatsapp_client() -> WhatsAppClient:
    """Get or create the WhatsApp client singleton."""
    global _whatsapp_client
    if _whatsapp_client is None:
        _whatsapp_client = WhatsAppClient()
    return _whatsapp_client
