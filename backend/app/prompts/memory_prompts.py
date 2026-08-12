"""
Memory Extraction Prompts
Used to instruct the AI to extract structured information from conversations
and update the contact's memory document automatically.
"""


MEMORY_EXTRACTION_PROMPT = """
You are a memory extraction system. Analyze the following conversation and extract 
structured information about the person sending the messages.

Return ONLY valid JSON with the following schema (omit fields you have no information about):

{
  "name": "string or null",
  "nickname": "string or null",
  "relationship": "family|friend|colleague|client|romantic|unknown or null",
  "profession": "string or null",
  "location": "string or null",
  "age": "number or null",
  "birthday": "YYYY-MM-DD or MM-DD or null",
  "favourite_things": ["array of strings"],
  "disliked_things": ["array of strings"],
  "preferred_language": "en|ur|roman_urdu|auto",
  "emoji_usage": "none|minimal|moderate|heavy",
  "reply_length": "short|medium|long",
  "conversation_tone": "formal|casual|funny|friendly|professional",
  "last_topic": "brief topic description or null",
  "last_topic_summary": "1-2 sentence summary of what was discussed or null",
  "ongoing_context": "brief description of active thread that needs continuation or null",
  "pending_questions": ["questions that were asked but not answered"],
  "relationship_summary": "1-2 sentence summary of relationship and history or null",
  "extracted_facts": {
    "key": "value pairs of any notable facts not covered above"
  }
}

Rules:
- Only include fields with actual information from the conversation
- Be conservative — only include what you're confident about
- preferred_language: detect from the writing style (roman_urdu if they mix Roman script with Urdu words)
- Return ONLY the JSON object, no other text
"""


def build_memory_update_prompt(
    conversation: list[dict[str, str]],
    existing_memory: dict | None = None,
) -> str:
    """
    Build the full prompt for memory extraction from a conversation.

    Args:
        conversation: List of {"role": "user/assistant", "content": str} messages.
        existing_memory: Current memory document to merge with.

    Returns:
        Complete prompt string for the AI.
    """
    conv_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}"
        for msg in conversation[-20:]  # Last 20 messages max
    )

    existing_context = ""
    if existing_memory:
        existing_context = f"""
Existing memory (update/merge with new information, don't remove existing data):
- Name: {existing_memory.get('name', 'unknown')}
- Relationship: {existing_memory.get('relationship', 'unknown')}
- Location: {existing_memory.get('location', 'unknown')}
- Favourite things: {existing_memory.get('favourite_things', [])}
"""

    return f"""
{MEMORY_EXTRACTION_PROMPT}

{existing_context}

CONVERSATION TO ANALYZE:
{conv_text}
"""


def build_topic_continuation_prompt(memory: dict) -> str:
    """
    Build a prompt to instruct AI to continue from where the conversation left off.

    Args:
        memory: Contact memory document.

    Returns:
        Prompt addition for topic continuation.
    """
    last_topic = memory.get("last_topic")
    last_summary = memory.get("last_topic_summary")
    ongoing = memory.get("ongoing_context")

    if not (last_topic or ongoing):
        return ""

    parts = ["\nThe user wants to continue. Here's the context:"]
    if last_topic:
        parts.append(f"- Previous topic: {last_topic}")
    if last_summary:
        parts.append(f"- Summary: {last_summary}")
    if ongoing:
        parts.append(f"- Ongoing context: {ongoing}")
    parts.append("Continue naturally from where you left off.")

    return "\n".join(parts)
