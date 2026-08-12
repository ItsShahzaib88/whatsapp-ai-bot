"""
Webhook Router Tests
Tests for WhatsApp webhook verification and message processing.
"""

import json
import pytest
from httpx import AsyncClient
from fastapi import FastAPI

from app.main import create_application
from app.core.config import settings


@pytest.fixture
def app() -> FastAPI:
    return create_application()


@pytest.fixture
async def client(app: FastAPI):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


class TestWebhookVerification:
    """Test WhatsApp webhook GET verification endpoint."""

    @pytest.mark.asyncio
    async def test_valid_verification(self, client: AsyncClient):
        """Should return hub.challenge for valid verify token."""
        response = await client.get(
            "/api/v1/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
                "hub.challenge": "test_challenge_12345",
            },
        )
        assert response.status_code == 200
        assert response.text == "test_challenge_12345"

    @pytest.mark.asyncio
    async def test_invalid_token(self, client: AsyncClient):
        """Should return 403 for wrong verify token."""
        response = await client.get(
            "/api/v1/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "WRONG_TOKEN",
                "hub.challenge": "challenge",
            },
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_mode(self, client: AsyncClient):
        """Should return 403 for wrong mode."""
        response = await client.get(
            "/api/v1/webhook",
            params={
                "hub.mode": "unsubscribe",
                "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
                "hub.challenge": "challenge",
            },
        )
        assert response.status_code == 403


class TestWebhookPayload:
    """Test webhook POST message processing."""

    @pytest.mark.asyncio
    async def test_text_message_returns_200(self, client: AsyncClient):
        """Should always return 200 for valid payloads."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "BUSINESS_ACCOUNT_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15550001234",
                                    "phone_number_id": "PHONE_NUMBER_ID",
                                },
                                "contacts": [
                                    {
                                        "profile": {"name": "Test User"},
                                        "wa_id": "15551234567",
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": "15551234567",
                                        "id": "wamid.test_message_id",
                                        "timestamp": "1700000000",
                                        "type": "text",
                                        "text": {"body": "Hello AI!"},
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        response = await client.post("/api/v1/webhook", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_non_whatsapp_object_ignored(self, client: AsyncClient):
        """Should return 200 but ignore non-WhatsApp objects."""
        response = await client.post(
            "/api/v1/webhook",
            json={"object": "instagram", "entry": []},
        )
        assert response.status_code == 200


class TestHealthCheck:
    """Test health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_endpoint_exists(self, client: AsyncClient):
        """Health endpoint should respond (may be degraded if no DB)."""
        response = await client.get("/api/v1/health")
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data
        assert "services" in data
