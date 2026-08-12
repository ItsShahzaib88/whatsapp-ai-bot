"""
Schedule and Log MongoDB Document Models
"""

from typing import Any

from pydantic import Field

from app.models.base import MongoBaseModel


class ScheduleModel(MongoBaseModel):
    """
    Auto-reply schedule document in the 'schedules' collection.
    Defines when specific auto-reply modes are active.
    """

    name: str
    mode: str
    # Options: office | meeting | driving | busy | vacation | night | custom

    # Custom auto-reply message for this mode
    auto_reply_message: str = ""

    # Schedule (cron-based)
    is_active: bool = True
    is_currently_active: bool = False  # Runtime state

    # Time-based activation
    cron_start: str | None = None  # Cron expression for start
    cron_end: str | None = None    # Cron expression for end
    timezone: str = "UTC"

    # Days of week (0=Mon, 6=Sun)
    active_days: list[int] = Field(default_factory=list)
    # Start/end times for simple time-based scheduling
    start_time: str | None = None  # "HH:MM" format
    end_time: str | None = None    # "HH:MM" format

    # Metadata
    description: str | None = None


class LogModel(MongoBaseModel):
    """
    Audit log document in the 'logs' collection.
    Tracks all significant system events. TTL index auto-deletes after 90 days.
    """

    level: str = "INFO"  # DEBUG | INFO | WARNING | ERROR | CRITICAL
    action: str  # e.g., "message_received", "ai_reply_sent", "webhook_verified"
    message: str

    # Context
    contact_id: str | None = None
    contact_phone: str | None = None
    user_id: str | None = None

    # Request context
    request_id: str | None = None
    ip_address: str | None = None
    path: str | None = None

    # Additional data (flexible)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Error details (if level is ERROR/CRITICAL)
    error_type: str | None = None
    error_traceback: str | None = None
