"""
Utility Helpers — General-purpose utility functions.
"""

import hashlib
import re
import unicodedata
from datetime import datetime, timezone


def normalize_phone_number(phone: str) -> str:
    """
    Normalize a phone number to E.164 format.
    Removes spaces, dashes, parentheses, and leading zeros.

    Args:
        phone: Raw phone number string.

    Returns:
        Cleaned phone number string (e.g., "923001234567").
    """
    # Remove all non-digit characters
    digits = re.sub(r"\D", "", phone)
    # Remove leading zeros for Pakistani numbers
    if digits.startswith("0") and len(digits) == 11:
        digits = "92" + digits[1:]
    return digits


def is_valid_phone(phone: str) -> bool:
    """Check if a phone number appears valid (7-15 digits)."""
    digits = re.sub(r"\D", "", phone)
    return 7 <= len(digits) <= 15


def truncate_text(text: str, max_length: int = 1024, suffix: str = "...") -> str:
    """Truncate text to a maximum length, appending suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def sha256_hash(text: str) -> str:
    """Compute SHA-256 hash of a string."""
    return hashlib.sha256(text.encode()).hexdigest()


def utcnow_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def detect_language(text: str) -> str:
    """
    Simple language detection based on character analysis.
    Returns: "ur" for Urdu script, "roman_urdu" for mixed, "en" for English.
    """
    urdu_chars = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
    total_chars = len(text.replace(" ", ""))
    if total_chars == 0:
        return "en"

    urdu_ratio = urdu_chars / total_chars

    if urdu_ratio > 0.3:
        return "ur"
    # Roman Urdu keywords
    roman_urdu_words = {
        "kya", "hai", "hain", "nahi", "aap", "tum", "mein", "yeh", "kaise",
        "theek", "achha", "shukriya", "khuda", "apka", "humara", "tera",
    }
    words = set(text.lower().split())
    if len(words & roman_urdu_words) >= 2:
        return "roman_urdu"

    return "en"
