"""
Memory Service — AI-powered contact memory extraction and update.
Automatically updates contact memory after each conversation using the AI.
"""

import json
from typing import Any

import structlog

from app.core.exceptions import AIProviderException
from app.prompts.memory_prompts import build_memory_update_prompt
from app.repositories.memory_repo import MemoryRepository
from app.services.ai_service import AIService

logger = structlog.get_logger(__name__)


class MemoryService:
    """
    Service responsible for managing per-contact AI memory.
    Uses AI to automatically extract structured information from conversations
    and update the memory document in MongoDB.
    """

    def __init__(
        self,
        memory_repo: MemoryRepository,
        ai_service: AIService,
    ) -> None:
        self._memory_repo = memory_repo
        self._ai_service = ai_service

    async def get_memory(self, contact_id: str) -> dict[str, Any] | None:
        """
        Get the current memory document for a contact.

        Args:
            contact_id: Contact's string ObjectId.

        Returns:
            Memory document dict or None.
        """
        return await self._memory_repo.find_by_contact(contact_id)

    async def update_memory_from_conversation(
        self,
        contact_id: str,
        conversation: list[dict[str, str]],
        existing_memory: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Use AI to extract information from a conversation and update memory.
        Called after each AI exchange (in background to avoid blocking the reply).

        Args:
            contact_id: Contact's string ObjectId.
            conversation: Recent conversation messages.
            existing_memory: Current memory document to merge into.

        Returns:
            Updated memory dict or None if extraction failed.
        """
        if len(conversation) < 2:
            # Not enough context to extract meaningful data
            return existing_memory

        try:
            extraction_prompt = build_memory_update_prompt(conversation, existing_memory)

            # Use the AI to extract memory
            response, _ = await self._ai_service.generate(
                messages=[{"role": "user", "content": extraction_prompt}],
                system_prompt=(
                    "You are a data extraction system. Return only valid JSON. "
                    "No markdown, no explanation, just the JSON object."
                ),
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=1024,
            )

            # Parse the JSON response
            extracted: dict[str, Any] = self._parse_json_response(response)
            if not extracted:
                logger.warning("Memory extraction returned empty JSON", contact_id=contact_id)
                return existing_memory

            # Merge with existing memory (don't overwrite with empty values)
            merged = self._merge_memory(existing_memory or {}, extracted)

            # Save to database
            await self._memory_repo.upsert_memory(contact_id, merged)
            await self._memory_repo.increment_conversation_count(contact_id)

            logger.debug(
                "Contact memory updated",
                contact_id=contact_id,
                fields_updated=list(extracted.keys()),
            )
            return merged

        except AIProviderException as e:
            logger.error("Memory update failed - AI error", contact_id=contact_id, error=str(e))
            return existing_memory

        except Exception as e:
            logger.error("Memory update failed", contact_id=contact_id, error=str(e))
            return existing_memory

    async def update_memory_field(
        self,
        contact_id: str,
        field: str,
        value: Any,
    ) -> bool:
        """
        Update a specific field in the contact's memory document.
        Used for admin edits from the dashboard.
        """
        return await self._memory_repo.update_one(
            await self._get_memory_id(contact_id),
            {field: value},
        ) if await self._get_memory_id(contact_id) else False

    async def _get_memory_id(self, contact_id: str) -> str | None:
        """Get the memory document ID for a contact."""
        memory = await self._memory_repo.find_by_contact(contact_id)
        return memory["id"] if memory else None

    async def update_topic_context(
        self,
        contact_id: str,
        last_topic: str,
        summary: str,
        ongoing_context: str | None = None,
    ) -> None:
        """
        Update the conversation topic context in memory.
        Called after each AI response.
        """
        update_data: dict[str, Any] = {
            "last_topic": last_topic,
            "last_topic_summary": summary,
        }
        if ongoing_context is not None:
            update_data["ongoing_context"] = ongoing_context

        await self._memory_repo.upsert_memory(contact_id, update_data)

    @staticmethod
    def _parse_json_response(response: str) -> dict[str, Any]:
        """
        Parse a JSON response from the AI, handling common formatting issues.
        """
        # Strip markdown code blocks if present
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])

        # Find JSON object boundaries
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse memory JSON", raw_response=response[:200])
            return {}

    @staticmethod
    def _merge_memory(
        existing: dict[str, Any],
        new_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Merge extracted data into existing memory.
        Preserves existing data; only updates with non-empty new values.
        Lists are merged (union), not replaced.
        """
        merged = dict(existing)

        for key, value in new_data.items():
            if value is None or value == "" or value == []:
                continue  # Don't overwrite with empty values

            if isinstance(value, list) and isinstance(existing.get(key), list):
                # Merge lists (avoid duplicates)
                existing_list = existing[key]
                merged[key] = list(dict.fromkeys(existing_list + value))
            elif isinstance(value, dict) and isinstance(existing.get(key), dict):
                # Merge dicts
                merged[key] = {**existing[key], **value}
            else:
                # Direct update
                merged[key] = value

        return merged
