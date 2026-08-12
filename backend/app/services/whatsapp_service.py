"""
WhatsApp Service — Main orchestration layer for incoming messages.
Coordinates AI replies, memory, voice processing, web search, and commands.
"""

import asyncio
from datetime import datetime
from typing import Any

import structlog

from app.core.config import settings
from app.core.exceptions import WhatsAppException
from app.database.mongodb import get_database
from app.prompts.system_prompts import build_system_prompt, build_command_response
from app.repositories.contact_repo import ContactRepository
from app.repositories.memory_repo import MemoryRepository, PersonalityRepository
from app.repositories.message_repo import MessageRepository
from app.services.ai_service import get_ai_service
from app.services.memory_service import MemoryService
from app.whatsapp.client import get_whatsapp_client
from app.whatsapp.webhook import (
    is_command_message,
    is_continuation_message,
    requires_web_search,
)

logger = structlog.get_logger(__name__)


class WhatsAppService:
    """
    Central orchestration service for processing WhatsApp webhook events.
    Handles the complete flow: receive → classify → AI reply → send.
    """

    async def process_internal_message(self, phone: str, text: str, name: str) -> str | None:
        """
        Process a message coming from the internal Node.js bridge (personal WhatsApp bot).
        Returns:
            - AI reply string if AI is enabled for this contact
            - None if AI is disabled (bridge will silently skip sending)
        """
        db = get_database()
        contact_repo = ContactRepository(db)
        message_repo = MessageRepository(db)
        memory_repo = MemoryRepository(db)
        personality_repo = PersonalityRepository(db)
        ai_service = get_ai_service()
        memory_service = MemoryService(memory_repo, ai_service)

        # ---- 1. Get or create contact ----
        contact, is_new = await contact_repo.get_or_create_by_phone(phone, "personal_bot", wa_name=name)
        contact_id = contact["id"]

        logger.info(
            "Internal message received",
            phone=phone,
            contact_id=contact_id,
            is_new_contact=is_new,
        )

        # ---- 2. Check if AI is enabled for this contact (Dashboard toggle) ----
        if not contact.get("ai_enabled", True):
            logger.info(
                "AI disabled for contact — skipping reply (toggled off from Dashboard)",
                contact_id=contact_id,
                phone=phone,
            )
            # Still save the inbound message to keep history, but return None
            await message_repo.insert_one({
                "contact_id": contact_id,
                "wa_message_id": f"internal_{datetime.now().timestamp()}",
                "direction": "inbound",
                "message_type": "text",
                "content": text,
                "status": "delivered",
                "raw_payload": {"source": "nodejs_bridge"},
            })
            await contact_repo.increment_message_count(contact_id, "inbound")
            return None  # Bridge will skip sending any reply

        # ---- 3. Check auto_reply_mode ----
        auto_mode = contact.get("auto_reply_mode", "ai")
        if auto_mode == "human":
            logger.info(
                "Contact in human mode — no AI reply",
                contact_id=contact_id,
            )
            await message_repo.insert_one({
                "contact_id": contact_id,
                "wa_message_id": f"internal_{datetime.now().timestamp()}",
                "direction": "inbound",
                "message_type": "text",
                "content": text,
                "status": "delivered",
                "raw_payload": {"source": "nodejs_bridge"},
            })
            await contact_repo.increment_message_count(contact_id, "inbound")
            return None

        # ---- 4. Save inbound message ----
        message_data: dict[str, Any] = {
            "contact_id": contact_id,
            "wa_message_id": f"internal_{datetime.now().timestamp()}",
            "direction": "inbound",
            "message_type": "text",
            "content": text,
            "status": "delivered",
            "raw_payload": {"source": "nodejs_bridge"},
        }
        await message_repo.insert_one(message_data)
        await contact_repo.increment_message_count(contact_id, "inbound")

        # ---- 5. Handle /commands (e.g. /help, /status, /reset, /memory) ----
        is_cmd, cmd_name = is_command_message(text)
        if is_cmd:
            cmd_reply = await self._handle_command_internal(
                cmd_name, contact, contact_repo, ai_service
            )
            # Save command reply
            await message_repo.insert_one({
                "contact_id": contact_id,
                "wa_message_id": f"internal_cmd_{datetime.now().timestamp()}",
                "direction": "outbound",
                "message_type": "text",
                "content": cmd_reply,
                "status": "sent",
                "ai_provider_used": "system",
                "is_voice_reply": False,
            })
            await contact_repo.increment_message_count(contact_id, "outbound")
            return cmd_reply

        # ---- 6. Load memory and personality ----
        memory = await memory_service.get_memory(contact_id)
        personality = None
        if contact.get("personality_id"):
            personality = await personality_repo.find_by_id(contact["personality_id"])
        if not personality:
            personality = await personality_repo.get_default()

        # ---- 7. Context window ----
        context_messages = await message_repo.get_context_messages(
            contact_id, limit=settings.GEMINI_MAX_TOKENS // 200
        )

        # ---- 8. Check for web search need ----
        web_search_context = None
        if settings.AUTO_FALLBACK_ENABLED and requires_web_search(text):
            web_search_context = await self._perform_web_search(text)

        # ---- 9. Build system prompt ----
        system_prompt = build_system_prompt(
            personality=personality,
            memory=memory,
            auto_reply_mode=auto_mode,
            web_search_context=web_search_context,
        )

        context_messages.append({"role": "user", "content": text})

        # ---- 10. Generate AI reply ----
        try:
            ai_response, provider_used = await ai_service.generate(
                messages=context_messages,
                system_prompt=system_prompt,
            )
        except Exception as e:
            logger.error("AI generation failed completely", error=str(e))
            ai_response = "Sorry, I'm having trouble responding right now."
            provider_used = "none"

        # ---- 11. Save outbound message ----
        outbound_data: dict[str, Any] = {
            "contact_id": contact_id,
            "wa_message_id": f"internal_reply_{datetime.now().timestamp()}",
            "direction": "outbound",
            "message_type": "text",
            "content": ai_response,
            "status": "sent",
            "ai_provider_used": provider_used,
            "is_voice_reply": False,
            "requires_web_search": web_search_context is not None,
        }
        await message_repo.insert_one(outbound_data)
        await contact_repo.increment_message_count(contact_id, "outbound")

        # ---- 12. Update memory in background ----
        all_messages = context_messages + [{"role": "assistant", "content": ai_response}]
        asyncio.create_task(
            memory_service.update_memory_from_conversation(
                contact_id=contact_id,
                conversation=all_messages,
                existing_memory=memory,
            )
        )

        return ai_response

    async def process_message_event(self, event: dict[str, Any]) -> None:
        """
        Process a parsed incoming message event from the webhook.
        Full pipeline: contact lookup → command check → AI reply → memory update.

        Args:
            event: Normalized message event dict from WebhookParser.
        """
        phone = event.get("phone_number", "")
        wa_message_id = event.get("wa_message_id", "")
        wa_name = event.get("wa_name")
        msg_type = event.get("message_type", "text")
        content = event.get("content", "")

        if not phone:
            logger.warning("Received message without phone number")
            return

        db = get_database()
        contact_repo = ContactRepository(db)
        message_repo = MessageRepository(db)
        memory_repo = MemoryRepository(db)
        personality_repo = PersonalityRepository(db)
        wa_client = get_whatsapp_client()
        ai_service = get_ai_service()
        memory_service = MemoryService(memory_repo, ai_service)

        # ---- 1. Get or create contact ----
        contact, is_new = await contact_repo.get_or_create_by_phone(phone, wa_name)
        contact_id = contact["id"]

        logger.info(
            "Message received",
            phone=phone,
            contact_id=contact_id,
            msg_type=msg_type,
            is_new_contact=is_new,
        )

        # ---- 2. Mark message as read ----
        if wa_message_id:
            asyncio.create_task(wa_client.mark_message_as_read(wa_message_id))

        # ---- 3. Handle voice notes ----
        if msg_type == "audio" and event.get("media_id"):
            content = await self._process_voice_note(event["media_id"], contact)
            if not content:
                await wa_client.send_text_message(
                    phone, "Sorry, I couldn't understand your voice note. Please try again."
                )
                return

        # ---- 4. Save inbound message ----
        message_data: dict[str, Any] = {
            "contact_id": contact_id,
            "wa_message_id": wa_message_id,
            "wa_timestamp": event.get("wa_timestamp"),
            "direction": "inbound",
            "message_type": msg_type,
            "content": content,
            "status": "delivered",
            "raw_payload": event,
        }
        await message_repo.insert_one(message_data)
        await contact_repo.increment_message_count(contact_id, "inbound")

        # ---- 5. Check if AI is enabled for this contact ----
        if not contact.get("ai_enabled", True):
            logger.info("AI disabled for contact, skipping reply", contact_id=contact_id)
            return

        # ---- 6. Check auto-reply mode ----
        auto_mode = contact.get("auto_reply_mode", "ai")
        if auto_mode == "human":
            logger.info("Contact in human mode, no AI reply", contact_id=contact_id)
            return

        # ---- 7. Handle /commands ----
        is_cmd, cmd_name = is_command_message(content)
        if is_cmd:
            await self._handle_command(cmd_name, contact, contact_repo, wa_client, ai_service)
            return

        # ---- 8. Load memory and personality ----
        memory = await memory_service.get_memory(contact_id)
        personality = None

        if contact.get("personality_id"):
            personality = await personality_repo.find_by_id(contact["personality_id"])
        if not personality:
            personality = await personality_repo.get_default()

        # ---- 9. Get conversation history for context window ----
        context_messages = await message_repo.get_context_messages(
            contact_id, limit=settings.GEMINI_MAX_TOKENS // 200  # Approx 10 messages
        )

        # ---- 10. Check if web search is needed ----
        web_search_context = None
        if settings.AUTO_FALLBACK_ENABLED and requires_web_search(content):
            web_search_context = await self._perform_web_search(content)

        # ---- 11. Check for continuation request ----
        extra_context = ""
        if is_continuation_message(content) and memory:
            from app.prompts.memory_prompts import build_topic_continuation_prompt
            extra_context = build_topic_continuation_prompt(memory)

        # ---- 12. Build system prompt ----
        system_prompt = build_system_prompt(
            personality=personality,
            memory=memory,
            auto_reply_mode=auto_mode,
            web_search_context=web_search_context,
        ) + extra_context

        # ---- 13. Generate AI reply ----
        # Add current message to context
        context_messages.append({"role": "user", "content": content})

        try:
            ai_response, provider_used = await ai_service.generate(
                messages=context_messages,
                system_prompt=system_prompt,
            )
        except Exception as e:
            logger.error("AI generation failed completely", error=str(e))
            ai_response = "Sorry, I'm having trouble responding right now. Please try again in a moment."
            provider_used = "none"

        # ---- 14. Send reply (text or voice) ----
        voice_enabled = contact.get("voice_reply_enabled", False)
        reply_wa_id = None

        if voice_enabled:
            reply_wa_id = await self._send_voice_reply(
                phone, ai_response, contact.get("preferred_language", "en"), wa_client
            )
        
        if not reply_wa_id:
            # Send as text (default or voice fallback)
            reply_result = await wa_client.send_text_message(phone, ai_response)
            reply_wa_id = reply_result.get("messages", [{}])[0].get("id")

        # ---- 15. Save outbound message ----
        outbound_data: dict[str, Any] = {
            "contact_id": contact_id,
            "wa_message_id": reply_wa_id,
            "direction": "outbound",
            "message_type": "voice" if voice_enabled and reply_wa_id else "text",
            "content": ai_response,
            "status": "sent",
            "ai_provider_used": provider_used,
            "requires_web_search": web_search_context is not None,
            "is_voice_reply": voice_enabled,
        }
        await message_repo.insert_one(outbound_data)
        await contact_repo.increment_message_count(contact_id, "outbound")

        # ---- 16. Update memory in background (non-blocking) ----
        all_messages = context_messages + [{"role": "assistant", "content": ai_response}]
        asyncio.create_task(
            memory_service.update_memory_from_conversation(
                contact_id=contact_id,
                conversation=all_messages,
                existing_memory=memory,
            )
        )

    async def process_status_event(self, event: dict[str, Any]) -> None:
        """
        Process a delivery/read status update event.
        Updates the message status in MongoDB.
        """
        wa_message_id = event.get("wa_message_id")
        status = event.get("status")

        if not wa_message_id or not status:
            return

        db = get_database()
        message_repo = MessageRepository(db)
        await message_repo.update_status(wa_message_id, status)
        logger.debug("Message status updated", wa_message_id=wa_message_id, status=status)

    async def _process_voice_note(
        self,
        media_id: str,
        contact: dict[str, Any],
    ) -> str | None:
        """
        Download and transcribe a voice note to text using STT.

        Returns:
            Transcribed text or None on failure.
        """
        try:
            from app.voice.stt import SpeechToTextService
            wa_client = get_whatsapp_client()

            # Download the voice note
            media_url = await wa_client.get_media_url(media_id)
            if not media_url:
                return None

            audio_bytes = await wa_client.download_media(media_url)
            if not audio_bytes:
                return None

            # Transcribe
            language = contact.get("preferred_language", "en")
            stt = SpeechToTextService()
            transcript = await stt.transcribe(audio_bytes, language=language)
            return transcript

        except Exception as e:
            logger.error("Voice note processing failed", media_id=media_id, error=str(e))
            return None

    async def _send_voice_reply(
        self,
        phone: str,
        text: str,
        language: str,
        wa_client,
    ) -> str | None:
        """
        Convert AI reply text to speech and send as voice message.

        Returns:
            WhatsApp message ID of the sent voice message, or None on failure.
        """
        try:
            from app.voice.tts import TextToSpeechService
            tts = TextToSpeechService()
            audio_path = await tts.synthesize(text, language=language)
            if not audio_path:
                return None

            result = await wa_client.send_audio_message(phone, audio_path)
            return result.get("messages", [{}])[0].get("id")
        except Exception as e:
            logger.error("Voice reply failed, falling back to text", error=str(e))
            return None

    async def _perform_web_search(self, query: str) -> str | None:
        """
        Perform a web search and return formatted results as context.

        Returns:
            Formatted search results string or None on failure.
        """
        try:
            from app.websearch.search_service import WebSearchService
            search_service = WebSearchService()
            results = await search_service.search(query)
            return results
        except Exception as e:
            logger.warning("Web search failed", query=query, error=str(e))
            return None

    async def _handle_command(
        self,
        command: str,
        contact: dict[str, Any],
        contact_repo: ContactRepository,
        wa_client,
        ai_service,
    ) -> None:
        """
        Handle a /command message from the user.
        """
        phone = contact["phone_number"]
        contact_id = contact["id"]

        if command == "help":
            response = build_command_response("help", {})
            await wa_client.send_text_message(phone, response)

        elif command == "ai":
            await contact_repo.update_one(contact_id, {"auto_reply_mode": "ai", "ai_enabled": True})
            await wa_client.send_text_message(phone, "✅ AI mode activated. I'll respond to your messages automatically.")

        elif command == "human":
            await contact_repo.update_one(contact_id, {"auto_reply_mode": "human"})
            await wa_client.send_text_message(phone, "👤 Switched to human mode. AI replies are disabled.")

        elif command == "voice":
            current = contact.get("voice_reply_enabled", False)
            await contact_repo.update_one(contact_id, {"voice_reply_enabled": not current})
            status = "enabled 🔊" if not current else "disabled 🔇"
            await wa_client.send_text_message(phone, f"Voice replies {status}")

        elif command == "status":
            response = build_command_response("status", {
                "ai_enabled": contact.get("ai_enabled", True),
                "provider": ai_service.get_active_provider_name(),
                "mode": contact.get("auto_reply_mode", "ai"),
                "voice_enabled": contact.get("voice_reply_enabled", False),
            })
            await wa_client.send_text_message(phone, response)

        elif command == "reset":
            db = get_database()
            memory_repo = MemoryRepository(db)
            memory = await memory_repo.find_by_contact(contact_id)
            if memory:
                await memory_repo.update_one(
                    memory["id"],
                    {"ongoing_context": None, "last_topic": None, "last_topic_summary": None}
                )
            await wa_client.send_text_message(phone, "🔄 Conversation context reset. Starting fresh!")

        elif command == "memory":
            db = get_database()
            memory_repo = MemoryRepository(db)
            memory = await memory_repo.find_by_contact(contact_id)
            if memory:
                mem_text = (
                    f"🧠 *My Memory About You*\n\n"
                    f"Name: {memory.get('name', 'Not known')}\n"
                    f"Relationship: {memory.get('relationship', 'Not known')}\n"
                    f"Favourite things: {', '.join(memory.get('favourite_things', ['Not known'])[:3])}\n"
                    f"Last topic: {memory.get('last_topic', 'None')}\n"
                    f"Conversations: {memory.get('total_conversations', 0)}"
                )
            else:
                mem_text = "I don't have any memory about you yet. Chat with me first!"
            await wa_client.send_text_message(phone, mem_text)

        elif command == "clear":
            db = get_database()
            memory_repo = MemoryRepository(db)
            memory = await memory_repo.find_by_contact(contact_id)
            if memory:
                await memory_repo.update_one(
                    memory["id"],
                    {
                        "favourite_things": [], "extracted_facts": {},
                         "relationship_summary": None, "ongoing_context": None,
                        "last_topic": None, "personal_notes": None,
                    }
                )
            await wa_client.send_text_message(phone, "🗑️ Memory cleared. I've forgotten our history (but not your profile).")

        elif command == "history":
            db = get_database()
            message_repo = MessageRepository(db)
            msgs = await message_repo.get_conversation_history(contact_id, limit=5)
            if msgs:
                history = "\n".join(
                    f"{'📥' if m['direction'] == 'inbound' else '📤'} {m.get('content', '')[:80]}"
                    for m in msgs
                )
                await wa_client.send_text_message(phone, f"📜 *Recent History*\n\n{history}")
            else:
                await wa_client.send_text_message(phone, "No message history found.")

        else:
            await wa_client.send_text_message(
                phone,
                f"❓ Unknown command: /{command}\n\nType /help to see available commands."
            )

    async def _handle_command_internal(
        self,
        command: str,
        contact: dict[str, Any],
        contact_repo: ContactRepository,
        ai_service,
    ) -> str:
        """
        Handle /command messages arriving from the Node.js bridge (personal bot flow).
        Returns the response as a string (bridge sends it via WhatsApp Web).
        No Meta API client needed — this is the unofficial bot path.
        """
        contact_id = contact["id"]

        if command == "help":
            return (
                "🤖 *AI Bot Commands*\n\n"
                "/help — Show this message\n"
                "/status — Your AI settings\n"
                "/memory — What I remember about you\n"
                "/reset — Clear conversation context\n"
                "/clear — Clear all memory\n"
                "/history — Recent messages\n\n"
                "💡 Tip: Toggle AI on/off per contact from the Dashboard."
            )

        elif command == "status":
            ai_enabled = contact.get("ai_enabled", True)
            mode = contact.get("auto_reply_mode", "ai")
            voice = contact.get("voice_reply_enabled", False)
            provider = ai_service.get_active_provider_name()
            return (
                f"📊 *Bot Status*\n\n"
                f"AI Enabled: {'✅ Yes' if ai_enabled else '❌ No'}\n"
                f"Mode: {mode.upper()}\n"
                f"Provider: {provider}\n"
                f"Voice: {'🔊 On' if voice else '🔇 Off'}"
            )

        elif command == "reset":
            db = get_database()
            memory_repo = MemoryRepository(db)
            memory = await memory_repo.find_by_contact(contact_id)
            if memory:
                await memory_repo.update_one(
                    memory["id"],
                    {"ongoing_context": None, "last_topic": None, "last_topic_summary": None}
                )
            return "🔄 Conversation context reset. Starting fresh!"

        elif command == "memory":
            db = get_database()
            memory_repo = MemoryRepository(db)
            memory = await memory_repo.find_by_contact(contact_id)
            if memory:
                return (
                    f"🧠 *My Memory About You*\n\n"
                    f"Name: {memory.get('name', 'Not known')}\n"
                    f"Relationship: {memory.get('relationship', 'Not known')}\n"
                    f"Favourite things: {', '.join(memory.get('favourite_things', ['Not known'])[:3])}\n"
                    f"Last topic: {memory.get('last_topic', 'None')}\n"
                    f"Conversations: {memory.get('total_conversations', 0)}"
                )
            return "I don't have any memory about you yet. Chat with me first!"

        elif command == "clear":
            db = get_database()
            memory_repo = MemoryRepository(db)
            memory = await memory_repo.find_by_contact(contact_id)
            if memory:
                await memory_repo.update_one(
                    memory["id"],
                    {
                        "favourite_things": [], "extracted_facts": {},
                        "relationship_summary": None, "ongoing_context": None,
                        "last_topic": None, "personal_notes": None,
                    }
                )
            return "🗑️ Memory cleared. I've forgotten our history (but not your profile)."

        elif command == "history":
            db = get_database()
            message_repo = MessageRepository(db)
            msgs = await message_repo.get_conversation_history(contact_id, limit=5)
            if msgs:
                history = "\n".join(
                    f"{'📥' if m['direction'] == 'inbound' else '📤'} {m.get('content', '')[:80]}"
                    for m in msgs
                )
                return f"📜 *Recent History*\n\n{history}"
            return "No message history found."

        else:
            return f"❓ Unknown command: /{command}\n\nType /help to see available commands."

