"""
Custom Exception Hierarchy
All application exceptions inherit from AppException for uniform handling.
"""

from typing import Any


class AppException(Exception):
    """
    Base application exception. All custom exceptions inherit from this.
    Provides structured error info for the global exception handler.
    """

    status_code: int = 500
    detail: str = "An internal error occurred"
    code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        detail: str | None = None,
        code: str | None = None,
        status_code: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.detail = detail or self.__class__.detail
        self.code = code or self.__class__.code
        self.status_code = status_code or self.__class__.status_code
        self.context = context or {}
        super().__init__(self.detail)


# ---- Authentication & Authorization ----

class AuthException(AppException):
    status_code = 401
    detail = "Authentication required"
    code = "UNAUTHORIZED"


class InvalidCredentialsException(AuthException):
    detail = "Invalid email or password"
    code = "INVALID_CREDENTIALS"


class TokenExpiredException(AuthException):
    detail = "Token has expired"
    code = "TOKEN_EXPIRED"


class ForbiddenException(AppException):
    status_code = 403
    detail = "Access forbidden"
    code = "FORBIDDEN"


# ---- Resource Errors ----

class NotFoundException(AppException):
    status_code = 404
    detail = "Resource not found"
    code = "NOT_FOUND"


class ContactNotFoundException(NotFoundException):
    detail = "Contact not found"
    code = "CONTACT_NOT_FOUND"


class MessageNotFoundException(NotFoundException):
    detail = "Message not found"
    code = "MESSAGE_NOT_FOUND"


class PersonalityNotFoundException(NotFoundException):
    detail = "Personality not found"
    code = "PERSONALITY_NOT_FOUND"


# ---- Validation Errors ----

class ValidationException(AppException):
    status_code = 422
    detail = "Validation error"
    code = "VALIDATION_ERROR"


class DuplicateException(AppException):
    status_code = 409
    detail = "Resource already exists"
    code = "DUPLICATE"


# ---- External Service Errors ----

class WhatsAppException(AppException):
    status_code = 502
    detail = "WhatsApp API error"
    code = "WHATSAPP_ERROR"


class AIProviderException(AppException):
    status_code = 503
    detail = "AI provider unavailable"
    code = "AI_PROVIDER_ERROR"


class AIQuotaExceededException(AIProviderException):
    detail = "AI provider quota exceeded"
    code = "AI_QUOTA_EXCEEDED"


class VoiceProcessingException(AppException):
    status_code = 500
    detail = "Voice processing failed"
    code = "VOICE_ERROR"


class WebSearchException(AppException):
    status_code = 503
    detail = "Web search service unavailable"
    code = "SEARCH_ERROR"


# ---- Rate Limiting ----

class RateLimitException(AppException):
    status_code = 429
    detail = "Too many requests"
    code = "RATE_LIMIT_EXCEEDED"


# ---- Webhook ----

class WebhookVerificationException(AppException):
    status_code = 403
    detail = "Webhook verification failed"
    code = "WEBHOOK_VERIFICATION_FAILED"
