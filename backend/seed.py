"""
Seed Script — Creates default admin user and default personality.
Run once to initialize the database:
    cd backend
    python seed.py
"""

import asyncio
import sys
import os

# Ensure we can import app modules
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings
from app.core.logging import configure_logging
from app.database.mongodb import connect_mongo, close_mongo, get_database
from app.repositories.user_repo import UserRepository
from app.repositories.memory_repo import PersonalityRepository
from app.services.auth_service import AuthService


async def seed():
    configure_logging()
    print("Connecting to MongoDB...")
    await connect_mongo()
    db = get_database()
    print(f"Connected to: {settings.MONGODB_URL} / {settings.MONGODB_DB_NAME}")

    # ---- Admin User ----
    user_repo = UserRepository(db)
    auth_service = AuthService(user_repo)

    existing_count = await user_repo.count()
    if existing_count > 0:
        print(f"Admin users already exist ({existing_count} found). Skipping user creation.")
    else:
        await auth_service.register(
            name=settings.ADMIN_NAME,
            email=settings.ADMIN_EMAIL,
            password=settings.ADMIN_PASSWORD,
        )
        print(f"Default admin created: {settings.ADMIN_EMAIL} / {settings.ADMIN_PASSWORD}")

    # ---- Default Personality ----
    personality_repo = PersonalityRepository(db)
    default = await personality_repo.get_default()
    if default:
        print(f"Default personality already exists: '{default['display_name']}'")
    else:
        await personality_repo.insert_one({
            "name": "assistant",
            "display_name": "Friendly Assistant",
            "tone": "friendly",
            "language_style": "balanced",
            "reply_length": "medium",
            "emoji_usage": "moderate",
            "persona_instructions": (
                "You are a helpful, warm, and intelligent AI assistant. "
                "Be conversational, concise, and always culturally respectful. "
                "Support English, Urdu, and Roman Urdu naturally. "
                "Use emojis moderately to keep the tone friendly."
            ),
            "greeting_style": "Warm and welcoming",
            "signoff_style": "Helpful and encouraging",
            "avoid_topics": [],
            "is_default": True,
            "is_active": True,
        })
        print("Default personality 'Friendly Assistant' created.")

    await close_mongo()
    print("\nSeeding complete!")
    print(f"\nLogin at: http://localhost:8000/dashboard")
    print(f"  Email: {settings.ADMIN_EMAIL}")
    print(f"  Password: {settings.ADMIN_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
