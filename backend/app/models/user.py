"""
User MongoDB Document Model
Represents admin users who manage the WhatsApp assistant dashboard.
"""

from datetime import datetime

from pydantic import EmailStr, Field

from app.models.base import MongoBaseModel


class UserModel(MongoBaseModel):
    """
    Admin user document stored in the 'users' collection.
    Only admins can access the dashboard and configure the system.
    """

    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    hashed_password: str
    is_active: bool = True
    is_superuser: bool = False
    last_login: datetime | None = None
    avatar_url: str | None = None

    # Dashboard preferences
    theme: str = "dark"  # "dark" | "light"
    timezone: str = "UTC"

    # Audit fields
    login_count: int = 0
    failed_login_count: int = 0
    last_failed_login: datetime | None = None
