"""Testes iniciais da central WhatsApp."""
import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import uazapi_client


async def _register(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "whatsapp@example.com", "password": "securepassword123", "full_name": "WhatsApp User"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_whatsapp_terms_are_public_and_versioned(client: AsyncClient):
    response = await client.get("/api/v1/whatsapp/terms")
    assert response.status_code == 200
    assert response.json()["version"] == settings.WHATSAPP_TERMS_VERSION
    assert "não oficial" in response.json()["text"]


@pytest.mark.asyncio
async def test_whatsapp_status_requires_authentication(client: AsyncClient):
    response = await client.get("/api/v1/whatsapp/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cannot_create_session_without_current_consent(client: AsyncClient):
    token = await _register(client)
    response = await client.post("/api/v1/whatsapp/session", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_accept_terms_and_create_session(client: AsyncClient, monkeypatch):
    token = await _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    terms = await client.get("/api/v1/whatsapp/terms")
    accepted = await client.post(
        "/api/v1/whatsapp/consent",
        headers=headers,
        json={"accepted": True, "terms_version": terms.json()["version"]},
    )
    assert accepted.status_code == 200
    assert accepted.json()["accepted"] is True

    async def fake_create_instance(name: str):
        return {"name": name, "status": "STOPPED", "token": "test-instance-token"}

    monkeypatch.setattr(uazapi_client, "create_instance", fake_create_instance)
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "UAZAPI_ADMIN_TOKEN", SecretStr("test-admin-token"))

    created = await client.post("/api/v1/whatsapp/session", headers=headers)
    assert created.status_code == 201
    assert created.json()["created"] is True
    assert created.json()["status"] == "STOPPED"

    status_response = await client.get("/api/v1/whatsapp/status", headers=headers)
    assert status_response.status_code == 200
    assert status_response.json()["terms_accepted"] is True
    assert status_response.json()["session"]["name"] == created.json()["name"]


@pytest.mark.asyncio
async def test_whatsapp_webhook_rejects_requests_without_secret(client: AsyncClient):
    response = await client.post(
        "/api/v1/whatsapp/webhook",
        json={"event": "message", "session": "tc_invalid", "payload": {}},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_whatsapp_conversations_require_authentication(client: AsyncClient):
    response = await client.get("/api/v1/whatsapp/conversations")
    assert response.status_code == 401
