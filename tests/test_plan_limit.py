"""
Tests for the free-plan client limit and the current-subscription endpoint.
The external clients API is simulated with an httpx MockTransport.
"""

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

import app.api.v1.integracao as integracao
from app.core.plans import FREE_CLIENT_LIMIT
from app.models.subscription import Subscription

CLIENTE = {"nome": "Cliente Teste", "telefone": "11999999999"}


async def _register(client: AsyncClient, email: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepassword123", "full_name": "Plan User"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _mock_clientes_api(monkeypatch, total_existentes: int) -> list:
    """Replace the external API; returns the list of created clients."""
    criados: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/order/listar-clientes"):
            return httpx.Response(200, json=[{"id": i} for i in range(total_existentes)])
        if request.url.path.endswith("/order/cadastro-cliente"):
            criados.append(request)
            return httpx.Response(200, json={"message": "ok"})
        return httpx.Response(404)

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        integracao.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    monkeypatch.setenv("CLIENTES_API_KEY", "test-key")
    monkeypatch.setenv("CLIENTES_API_URL", "http://clientes.test")
    monkeypatch.setenv("INTEGRATION_SECRET", "test-integration-secret")
    return criados


@pytest.mark.asyncio
async def test_free_user_blocked_at_limit(client: AsyncClient, monkeypatch):
    headers = await _register(client, "free-limit@example.com")
    criados = _mock_clientes_api(monkeypatch, total_existentes=FREE_CLIENT_LIMIT)

    response = await client.post("/api/v1/integracao/cadastro-cliente", json=CLIENTE, headers=headers)

    assert response.status_code == 403
    assert "Free" in response.json()["detail"]
    assert criados == []


@pytest.mark.asyncio
async def test_free_user_can_create_below_limit(client: AsyncClient, monkeypatch):
    headers = await _register(client, "free-ok@example.com")
    criados = _mock_clientes_api(monkeypatch, total_existentes=FREE_CLIENT_LIMIT - 1)

    response = await client.post("/api/v1/integracao/cadastro-cliente", json=CLIENTE, headers=headers)

    assert response.status_code == 200
    assert len(criados) == 1


@pytest.mark.asyncio
async def test_paid_user_has_no_limit(client: AsyncClient, db_session, monkeypatch):
    headers = await _register(client, "pro-user@example.com")
    result = await db_session.execute(select(Subscription))
    for subscription in result.scalars().all():
        subscription.plan_name = "pro"
    await db_session.commit()
    criados = _mock_clientes_api(monkeypatch, total_existentes=FREE_CLIENT_LIMIT + 10)

    response = await client.post("/api/v1/integracao/cadastro-cliente", json=CLIENTE, headers=headers)

    assert response.status_code == 200
    assert len(criados) == 1


@pytest.mark.asyncio
async def test_current_subscription_returns_free_plan(client: AsyncClient):
    headers = await _register(client, "current-sub@example.com")

    response = await client.get("/api/v1/subscriptions/current", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["plan_name"] == "free"
    assert data["status"] == "active"
