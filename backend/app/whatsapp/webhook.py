"""
WhatsApp Webhook Parser
Parses incoming webhook payloads from the WhatsApp Cloud API.
Handles all message types, status updates, and verification requests.
"""

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class WebhookParser:
    """
    Parses WhatsApp Cloud API webhook payloads into structured data.
    WhatsApp sends nested JSON objects; this class flattens and normalizes them.
    """

    @staticmethod
    def parse_webhook(payload: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Parse a full webhook payload and return a list of events.

        Each event is a normalized dict with:
        - type: "message" | "status" | "unknown"
        - For messages: phone_number, wa_message_id, message_type, content, etc.
        - For status: wa_message_id, status

        Args:
            payload: Raw webhook JSON body from WhatsApp.

        Returns:
            List of parsed event dicts.
        """
        events: list[dict[str, Any]] = []

        entries = payload.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                if not isinstance(value, dict):
                    continue

                # Parse incoming messages
                messages = value.get("messages", [])
                contacts_info = value.get("contacts", [])

                for message in messages:
                    event = WebhookParser._parse_message(message, contacts_info)
                    if event:
                        events.append(event)

                # Parse status updates (delivery, read receipts)
                statuses = value.get("statuses", [])
                for status in statuses:
                    event = WebhookParser._parse_status(status)
                    if event:
                        events.append(event)

        return events

    @staticmethod
    def _parse_message(
        message: dict[str, Any],
        contacts_info: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Parse a single message object from the webhook payload."""
        msg_type = message.get("type")
        phone = message.get("from", "")
        wa_message_id = message.get("id", "")
        timestamp = message.get("timestamp", "")

        # Get display name from contacts info
        wa_name = None
        for contact in contacts_info:
            if contact.get("wa_id") == phone:
                wa_name = contact.get("profile", {}).get("name")
                break

        # Build base event
        event: dict[str, Any] = {
            "type": "message",
            "phone_number": phone,
            "wa_message_id": wa_message_id,
            "wa_timestamp": timestamp,
            "message_type": msg_type,
            "wa_name": wa_name,
            "content": "",
            "media_id": None,
            "media_mime_type": None,
        }

        # ---- Extract content by message type ----
        if msg_type == "text":
            text_obj = message.get("text", {})
            event["content"] = text_obj.get("body", "")

        elif msg_type == "audio":
            audio_obj = message.get("audio", {})
            event["media_id"] = audio_obj.get("id")
            event["media_mime_type"] = audio_obj.get("mime_type", "audio/ogg")
            event["is_voice_note"] = audio_obj.get("voice", False)

        elif msg_type == "image":
            image_obj = message.get("image", {})
            event["media_id"] = image_obj.get("id")
            event["content"] = image_obj.get("caption", "")
            event["media_mime_type"] = image_obj.get("mime_type", "image/jpeg")

        elif msg_type == "video":
            video_obj = message.get("video", {})
            event["media_id"] = video_obj.get("id")
            event["content"] = video_obj.get("caption", "")

        elif msg_type == "document":
            doc_obj = message.get("document", {})
            event["media_id"] = doc_obj.get("id")
            event["content"] = doc_obj.get("filename", "")

        elif msg_type == "location":
            loc_obj = message.get("location", {})
            lat = loc_obj.get("latitude")
            lng = loc_obj.get("longitude")
            name = loc_obj.get("name", "")
            event["content"] = f"Location: {name} ({lat}, {lng})"

        elif msg_type == "sticker":
            event["content"] = "[Sticker]"

        elif msg_type == "interactive":
            interactive = message.get("interactive", {})
            interactive_type = interactive.get("type")
            if interactive_type == "button_reply":
                event["content"] = interactive.get("button_reply", {}).get("title", "")
            elif interactive_type == "list_reply":
                event["content"] = interactive.get("list_reply", {}).get("title", "")

        elif msg_type == "button":
            event["content"] = message.get("button", {}).get("text", "")

        else:
            logger.warning("Unknown message type received", msg_type=msg_type)
            return None

        return event

    @staticmethod
    def _parse_status(status: dict[str, Any]) -> dict[str, Any] | None:
        """Parse a message status update event."""
        wa_message_id = status.get("id")
        status_value = status.get("status")  # sent | delivered | read | failed

        if not wa_message_id or not status_value:
            return None

        return {
            "type": "status",
            "wa_message_id": wa_message_id,
            "status": status_value,
            "timestamp": status.get("timestamp"),
            "recipient_id": status.get("recipient_id"),
        }


def is_continuation_message(text: str) -> bool:
    """
    Detect if a message is asking to continue the previous topic.

    Returns:
        True if the message appears to be a continuation request.
    """
    continuation_phrases = [
        "continue", "aage", "jari rakho", "آگے", "جاری", "carry on",
        "go on", "and then", "phir", "پھر", "continue karo",
        "continue kro", "baki", "باقی",
    ]
    text_lower = text.lower().strip()
    return any(phrase in text_lower for phrase in continuation_phrases)


def is_command_message(text: str) -> tuple[bool, str]:
    """
    Check if a message is a /command.

    Returns:
        Tuple of (is_command: bool, command_name: str)
    """
    text = text.strip()
    if text.startswith("/"):
        command = text.split()[0][1:].lower()
        return True, command
    return False, ""


def requires_web_search(text: str) -> bool:
    """
    Detect if a message likely needs web search for current information.
    Uses keyword matching to identify weather, news, sports, prices, etc.

    Returns:
        True if web search should be triggered.
    """
    search_keywords = [
        # Weather
        "weather", "mausam", "موسم", "temperature", "rain", "forecast",
        # Sports
        "match", "score", "cricket", "football", "ipl", "psl", "result",
        # News
        "news", "khabar", "خبر", "breaking", "latest",
        # Finance
        "price", "rate", "dollar", "euro", "gold", "silver", "bitcoin",
        "stock", "share", "forex",
        # Current events
        "today", "aaj", "آج", "yesterday", "kal", "current",
        "now", "abhi", "ابھی", "2024", "2025", "2026",
    ]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in search_keywords)
