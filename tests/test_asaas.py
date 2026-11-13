"""
Testes da integração de assinaturas com o Asaas.

A API do Asaas é simulada com httpx.MockTransport (nenhuma chamada real é feita).
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import select

from app.config import settings
from app.core.documents import is_valid_cpf_cnpj
from app.core.plans import get_user_plan
from app.models.asaas import AsaasCheckout, AsaasWebhookEvent
from app.models.subscription import Subscription
from app.models.user import User
from app.services import asaas_client, asaas_service

WEBHOOK_TOKEN = "t" * 40
VALID_CPF = "529.982.247-25"
HEADERS_WEBHOOK = {"asaas-access-token": WEBHOOK_TOKEN}


@pytest.fixture(autouse=True)
def asaas_settings(monkeypatch):
    monkeypatch.setattr(settings, "ASAAS_API_KEY", SecretStr("$aact_hmlg_test_key"))
    monkeypatch.setattr(settings, "ASAAS_ENVIRONMENT", "sandbox")
    monkeypatch.setattr(settings, "ASAAS_WEBHOOK_TOKEN", SecretStr(WEBHOOK_TOKEN))
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://app.example.com")


class FakeAsaas:
    """Servidor falso do Asaas: guarda as requisições recebidas."""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.existing_customers: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if request.method == "GET" and path.endswith("/customers"):
            return httpx.Response(200, json={"data": self.existing_customers})
        if request.method == "POST" and path.endswith("/customers"):
            return httpx.Response(200, json={"id": "cus_123"})
        if request.method == "PUT" and "/customers/" in path:
            return httpx.Response(200, json={"id": path.rsplit("/", 1)[-1]})
        if request.method == "POST" and path.endswith("/checkouts"):
            return httpx.Response(
                200, json={"id": "chk_123", "link": "https://sandbox.asaas.com/checkoutSession/show/chk_123"}
            )
        if request.method == "DELETE" and "/subscriptions/" in path:
            return httpx.Response(200, json={"deleted": True, "id": path.rsplit("/", 1)[-1]})
        return httpx.Response(404, json={"errors": [{"description": "não encontrado"}]})

    def calls(self, method: str, suffix: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.method == method and r.url.path.endswith(suffix)]


@pytest.fixture
def fake_asaas(monkeypatch) -> FakeAsaas:
    fake = FakeAsaas()
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(fake)
    monkeypatch.setattr(asaas_client.httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs))
    return fake


async def _register(client: AsyncClient, email: str) -> dict:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepassword123", "full_name": "Cliente Asaas"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _user(db_session, email: str) -> User:
    result = await db_session.execute(select(User).where(User.email == email).execution_options(populate_existing=True))
    return result.scalar_one()


async def _sub(db_session, user_id) -> Subscription:
    result = await db_session.execute(
        select(Subscription).where(Subscription.user_id == user_id).execution_options(populate_existing=True)
    )
    return result.scalars().first()


async def _make_pro(db_session, email: str, *, sub_id="sub_1", customer="cus_1", days=10, status="active"):
    """Deixa o usuário no plano Pro, com assinatura e cliente do Asaas já vinculados."""
    user = await _user(db_session, email)
    user.asaas_customer_id = customer
    row = await _sub(db_session, user.id)
    row.plan_name = "pro"
    row.status = status
    row.asaas_subscription_id = sub_id
    row.current_period_end = datetime.now(timezone.utc) + timedelta(days=days)
    await db_session.commit()
    return user


def _event(event: str, **body) -> dict:
    return {"id": f"evt_{uuid.uuid4().hex}", "event": event, **body}


async def _send(client: AsyncClient, payload: dict, headers: dict | None = None):
    return await client.post("/api/v1/subscriptions/webhook/asaas", json=payload, headers=headers or HEADERS_WEBHOOK)


# ── Documentos ───────────────────────────────────────────────


def test_cpf_cnpj_validation():
    assert is_valid_cpf_cnpj("529.982.247-25")
    assert is_valid_cpf_cnpj("52998224725")
    assert is_valid_cpf_cnpj("11.222.333/0001-81")
    assert not is_valid_cpf_cnpj("111.111.111-11")
    assert not is_valid_cpf_cnpj("529.982.247-24")
    assert not is_valid_cpf_cnpj("")


# ── Planos ───────────────────────────────────────────────────


async def test_plans_catalog(client: AsyncClient):
    response = await client.get("/api/v1/subscriptions/plans")
    assert response.status_code == 200
    plans = {p["name"]: p for p in response.json()}
    assert plans["free"]["price_monthly"] == 0
    assert plans["pro"]["price_monthly"] == 24.9
    assert plans["pro"]["purchasable"] is True
    assert plans["free"]["purchasable"] is False
    assert plans["enterprise"]["purchasable"] is False


# ── Checkout ─────────────────────────────────────────────────


@pytest.mark.parametrize("plan", ["free", "enterprise", "inexistente"])
async def test_checkout_rejects_unavailable_plans(client: AsyncClient, fake_asaas, plan):
    headers = await _register(client, f"plan-{plan}@example.com")
    response = await client.post("/api/v1/subscriptions/checkout", json={"plan": plan}, headers=headers)
    assert response.status_code == 400
    assert fake_asaas.requests == []


async def test_checkout_creates_customer_and_hosted_checkout(client: AsyncClient, db_session, fake_asaas):
    email = "buyer@example.com"
    headers = await _register(client, email)

    # O cliente tenta mandar valor e URLs próprios: o backend deve ignorar.
    body = {
        "plan": "pro", "cpf_cnpj": VALID_CPF, "phone": "27999998888",
        "address": "Rua das Flores", "address_number": "123", "postal_code": "29900000",
        "province": "Centro", "city": "3204906",
        "price": 1, "value": 1, "success_url": "https://evil.example",
    }
    response = await client.post("/api/v1/subscriptions/checkout", json=body, headers=headers)

    assert response.status_code == 200
    assert response.json()["checkout_url"] == "https://sandbox.asaas.com/checkoutSession/show/chk_123"

    customer_req = fake_asaas.calls("POST", "/customers")[0]
    customer_body = json.loads(customer_req.content)
    assert customer_body["cpfCnpj"] == "52998224725"  # só dígitos
    assert customer_body["email"] == email
    assert customer_body["phone"] == "27999998888"
    assert customer_body["address"] == "Rua das Flores"
    assert customer_body["addressNumber"] == "123"
    assert customer_body["postalCode"] == "29900000"
    assert customer_body["province"] == "Centro"

    checkout_req = fake_asaas.calls("POST", "/checkouts")[0]
    sent = json.loads(checkout_req.content)
    assert checkout_req.headers["access_token"] == "$aact_hmlg_test_key"
    assert checkout_req.headers["user-agent"] == "TexasCRM/1.0"
    assert sent["chargeTypes"] == ["RECURRENT"]
    assert sent["billingTypes"] == ["CREDIT_CARD"]
    assert sent["customer"] == "cus_123"
    assert sent["items"][0]["value"] == 24.9  # valor definido pelo backend
    assert sent["subscription"]["cycle"] == "MONTHLY"
    assert sent["callback"]["successUrl"].startswith("https://app.example.com/settings/billing")
    assert "evil" not in json.dumps(sent)

    user = await _user(db_session, email)
    assert user.asaas_customer_id == "cus_123"
    records = (await db_session.execute(select(AsaasCheckout))).scalars().all()
    assert [(r.checkout_id, r.user_id, r.plan_name, r.status) for r in records] == [
        ("chk_123", user.id, "pro", "ACTIVE")
    ]

    # Segundo clique: reaproveita o checkout ainda válido (nada novo é criado no Asaas).
    again = await client.post("/api/v1/subscriptions/checkout", json={"plan": "pro"}, headers=headers)
    assert again.status_code == 200
    assert len(fake_asaas.calls("POST", "/checkouts")) == 1
    assert len(fake_asaas.calls("POST", "/customers")) == 1


async def test_checkout_rejects_invalid_document(client: AsyncClient, fake_asaas):
    headers = await _register(client, "baddoc@example.com")
    response = await client.post(
        "/api/v1/subscriptions/checkout", json={"plan": "pro", "cpf_cnpj": "111.111.111-11"}, headers=headers
    )
    assert response.status_code == 400
    assert "CPF" in response.json()["detail"]
    assert fake_asaas.calls("POST", "/customers") == []


async def test_checkout_reuses_existing_asaas_customer(client: AsyncClient, db_session, fake_asaas):
    fake_asaas.existing_customers = [{"id": "cus_old"}]
    headers = await _register(client, "returning@example.com")

    body = {
        "plan": "pro", "cpf_cnpj": VALID_CPF, "phone": "27999998888",
        "address": "Rua das Flores", "address_number": "123", "postal_code": "29900000",
        "province": "Centro", "city": "3204906",
    }
    response = await client.post("/api/v1/subscriptions/checkout", json=body, headers=headers)

    assert response.status_code == 200
    assert fake_asaas.calls("POST", "/customers") == []
    assert len(fake_asaas.calls("PUT", "/customers/cus_old")) == 1
    updated = json.loads(fake_asaas.calls("PUT", "/customers/cus_old")[0].content)
    assert updated["phone"] == "27999998888"
    assert json.loads(fake_asaas.calls("POST", "/checkouts")[0].content)["customer"] == "cus_old"


async def test_checkout_without_api_key_is_unavailable(client: AsyncClient, monkeypatch, fake_asaas):
    monkeypatch.setattr(settings, "ASAAS_API_KEY", SecretStr(""))
    headers = await _register(client, "nokey@example.com")
    body = {
        "plan": "pro", "cpf_cnpj": VALID_CPF, "phone": "27999998888",
        "address": "Rua das Flores", "address_number": "123", "postal_code": "29900000",
        "province": "Centro", "city": "3204906",
    }
    response = await client.post("/api/v1/subscriptions/checkout", json=body, headers=headers)
    assert response.status_code == 502
    assert "indisponíveis" in response.json()["detail"]
    assert fake_asaas.requests == []


async def test_checkout_blocked_when_already_subscribed(client: AsyncClient, db_session, fake_asaas):
    email = "already@example.com"
    headers = await _register(client, email)
    await _make_pro(db_session, email)

    response = await client.post("/api/v1/subscriptions/checkout", json={"plan": "pro"}, headers=headers)

    assert response.status_code == 409
    assert fake_asaas.calls("POST", "/checkouts") == []


# ── Webhook: autenticação e idempotência ─────────────────────


async def test_webhook_fails_closed_without_configured_token(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "ASAAS_WEBHOOK_TOKEN", SecretStr(""))
    response = await _send(client, _event("PAYMENT_RECEIVED"), headers={"asaas-access-token": ""})
    assert response.status_code == 503


async def test_webhook_rejects_missing_or_wrong_token(client: AsyncClient):
    payload = _event("PAYMENT_RECEIVED")
    assert (await client.post("/api/v1/subscriptions/webhook/asaas", json=payload)).status_code == 401
    assert (await _send(client, payload, headers={"asaas-access-token": "errado"})).status_code == 401


async def test_webhook_rejects_api_key_as_token(client: AsyncClient):
    response = await _send(client, _event("PAYMENT_RECEIVED"), headers={"asaas-access-token": "$aact_hmlg_test_key"})
    assert response.status_code == 401


async def test_checkout_paid_activates_plan_once(client: AsyncClient, db_session):
    email = "paid@example.com"
    headers = await _register(client, email)
    user = await _user(db_session, email)
    db_session.add(
        AsaasCheckout(
            user_id=user.id,
            checkout_id="chk_paid",
            plan_name="pro",
            status="ACTIVE",
            link="https://x",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
    )
    await db_session.commit()

    # Voltar para a página de sucesso não confirma nada: o plano segue Free.
    assert (await client.get("/api/v1/subscriptions/current", headers=headers)).json()["plan_name"] == "free"

    event = _event("CHECKOUT_PAID", checkout={"id": "chk_paid", "status": "PAID", "customer": "cus_777"})
    first = await _send(client, event)
    second = await _send(client, event)  # o Asaas pode reenviar o mesmo evento

    assert first.json() == {"status": "processed"}
    assert second.json() == {"status": "duplicate"}
    current = (await client.get("/api/v1/subscriptions/current", headers=headers)).json()
    assert current["plan_name"] == "pro"
    assert current["status"] == "active"
    assert await get_user_plan(db_session, user.id) == "pro"
    events = (await db_session.execute(select(AsaasWebhookEvent))).scalars().all()
    assert len(events) == 1
    assert (await _user(db_session, email)).asaas_customer_id == "cus_777"


async def test_checkout_paid_for_unknown_checkout_changes_nothing(client: AsyncClient, db_session):
    email = "unknown-checkout@example.com"
    await _register(client, email)
    response = await _send(client, _event("CHECKOUT_PAID", checkout={"id": "chk_desconhecido"}))
    assert response.status_code == 200
    user = await _user(db_session, email)
    assert (await _sub(db_session, user.id)).plan_name == "free"


async def test_checkout_expired_and_canceled_do_not_activate(client: AsyncClient, db_session):
    email = "expired@example.com"
    await _register(client, email)
    user = await _user(db_session, email)
    db_session.add(AsaasCheckout(user_id=user.id, checkout_id="chk_exp", plan_name="pro", link="https://x"))
    await db_session.commit()

    await _send(client, _event("CHECKOUT_EXPIRED", checkout={"id": "chk_exp"}))

    record = (
        await db_session.execute(
            select(AsaasCheckout).where(AsaasCheckout.checkout_id == "chk_exp").execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert record.status == "EXPIRED"
    assert (await _sub(db_session, user.id)).plan_name == "free"


async def test_failed_processing_is_not_recorded_so_asaas_can_retry(client: AsyncClient, db_session, monkeypatch):
    email = "retry@example.com"
    await _register(client, email)
    event = _event("PAYMENT_RECEIVED", payment={"id": "pay_1", "subscription": "sub_1"})

    async def boom(*args, **kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(asaas_service, "_on_payment_event", boom)
    failed = await _send(client, event)
    assert failed.status_code == 500
    assert (await db_session.execute(select(AsaasWebhookEvent))).scalars().all() == []

    monkeypatch.undo()  # volta ao comportamento normal; o reenvio deve ser processado
    monkeypatch.setattr(settings, "ASAAS_WEBHOOK_TOKEN", SecretStr(WEBHOOK_TOKEN))
    retry = await _send(client, event)
    assert retry.json() == {"status": "processed"}


# ── Webhook: assinatura e cobranças ──────────────────────────


async def test_subscription_created_links_subscription_to_user(client: AsyncClient, db_session):
    email = "linked@example.com"
    await _register(client, email)
    user = await _user(db_session, email)
    user.asaas_customer_id = "cus_link"
    await db_session.commit()

    await _send(client, _event("SUBSCRIPTION_CREATED", subscription={"id": "sub_link", "customer": "cus_link"}))

    assert (await _sub(db_session, user.id)).asaas_subscription_id == "sub_link"


async def test_payment_lifecycle_overdue_then_received(client: AsyncClient, db_session):
    email = "lifecycle@example.com"
    await _register(client, email)
    user = await _make_pro(db_session, email, days=1)
    payment = {"id": "pay_1", "subscription": "sub_1", "customer": "cus_1", "value": 24.9}

    await _send(client, _event("PAYMENT_OVERDUE", payment={**payment, "dueDate": "2026-11-01"}))
    assert (await _sub(db_session, user.id)).status == "past_due"
    assert await get_user_plan(db_session, user.id) == "free"  # vencido: sem acesso Pro

    received = {**payment, "dueDate": "2026-11-01", "paymentDate": "2026-11-12"}
    await _send(client, _event("PAYMENT_RECEIVED", payment=received))
    row = await _sub(db_session, user.id)
    assert row.status == "active"
    assert row.plan_name == "pro"
    assert await get_user_plan(db_session, user.id) == "pro"
    assert row.current_period_end.date().isoformat() >= "2026-12-12"


async def test_card_declined_and_chargeback_block_access(client: AsyncClient, db_session):
    for index, event in enumerate(["PAYMENT_CREDIT_CARD_CAPTURE_REFUSED", "PAYMENT_CHARGEBACK_REQUESTED"]):
        email = f"blocked{index}@example.com"
        await _register(client, email)
        user = await _make_pro(db_session, email, sub_id=f"sub_b{index}", customer=f"cus_b{index}")
        await _send(client, _event(event, payment={"subscription": f"sub_b{index}", "customer": f"cus_b{index}"}))
        assert (await _sub(db_session, user.id)).status == "past_due"
        assert await get_user_plan(db_session, user.id) == "free"


async def test_refund_revokes_access(client: AsyncClient, db_session):
    email = "refund@example.com"
    await _register(client, email)
    user = await _make_pro(db_session, email)

    await _send(client, _event("PAYMENT_REFUNDED", payment={"subscription": "sub_1", "customer": "cus_1"}))

    assert await get_user_plan(db_session, user.id) == "free"
    assert (await _sub(db_session, user.id)).status == "canceled"


async def test_late_payment_does_not_reactivate_canceled_subscription(client: AsyncClient, db_session):
    email = "late@example.com"
    await _register(client, email)
    user = await _make_pro(db_session, email, status="canceled", days=-1)  # cancelada e período já acabou

    # Cartão: PAYMENT_RECEIVED chega ~32 dias depois da confirmação, mesmo após o cancelamento.
    await _send(
        client,
        _event(
            "PAYMENT_RECEIVED",
            payment={"subscription": "sub_1", "customer": "cus_1", "value": 24.9, "paymentDate": "2026-11-12"},
        ),
    )

    assert (await _sub(db_session, user.id)).status == "canceled"
    assert await get_user_plan(db_session, user.id) == "free"


async def test_subscription_deleted_keeps_access_until_paid_period_ends(client: AsyncClient, db_session):
    email = "deleted-paid@example.com"
    await _register(client, email)
    user = await _make_pro(db_session, email, days=10)

    await _send(client, _event("SUBSCRIPTION_DELETED", subscription={"id": "sub_1", "customer": "cus_1"}))

    row = await _sub(db_session, user.id)
    assert row.status == "canceled"
    assert row.plan_name == "pro"
    assert await get_user_plan(db_session, user.id) == "pro"  # ainda dentro do período pago


async def test_subscription_deleted_after_period_downgrades_to_free(client: AsyncClient, db_session):
    email = "deleted-expired@example.com"
    await _register(client, email)
    user = await _make_pro(db_session, email, days=-3)

    await _send(client, _event("SUBSCRIPTION_INACTIVATED", subscription={"id": "sub_1", "customer": "cus_1"}))

    row = await _sub(db_session, user.id)
    assert (row.status, row.plan_name) == ("canceled", "free")
    assert await get_user_plan(db_session, user.id) == "free"


async def test_events_from_old_subscription_are_ignored(client: AsyncClient, db_session):
    email = "old-sub@example.com"
    await _register(client, email)
    user = await _make_pro(db_session, email, sub_id="sub_new", customer="cus_1")

    await _send(client, _event("SUBSCRIPTION_DELETED", subscription={"id": "sub_antiga", "customer": "cus_1"}))
    await _send(client, _event("PAYMENT_OVERDUE", payment={"subscription": "sub_antiga", "customer": "cus_1"}))

    row = await _sub(db_session, user.id)
    assert (row.status, row.plan_name) == ("active", "pro")


async def test_unknown_customer_event_is_acknowledged_without_changes(client: AsyncClient):
    response = await _send(
        client, _event("PAYMENT_RECEIVED", payment={"id": "pay_x", "subscription": "sub_x", "customer": "cus_x"})
    )
    assert response.status_code == 200


async def test_one_off_payments_are_ignored(client: AsyncClient, db_session):
    email = "oneoff@example.com"
    await _register(client, email)
    user = await _user(db_session, email)
    user.asaas_customer_id = "cus_oneoff"
    await db_session.commit()

    await _send(client, _event("PAYMENT_RECEIVED", payment={"id": "pay_1", "customer": "cus_oneoff", "value": 24.9}))

    assert (await _sub(db_session, user.id)).plan_name == "free"


# ── Cancelamento ─────────────────────────────────────────────


async def test_cancel_stops_asaas_billing_and_keeps_paid_access(client: AsyncClient, db_session, fake_asaas):
    email = "cancel@example.com"
    headers = await _register(client, email)
    user = await _make_pro(db_session, email, days=10)

    response = await client.post("/api/v1/subscriptions/cancel", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "canceled"
    assert response.json()["access_until"] is not None
    assert len(fake_asaas.calls("DELETE", "/subscriptions/sub_1")) == 1
    assert await get_user_plan(db_session, user.id) == "pro"


async def test_cancel_requires_a_subscription(client: AsyncClient, fake_asaas):
    headers = await _register(client, "nothing-to-cancel@example.com")
    response = await client.post("/api/v1/subscriptions/cancel", headers=headers)
    assert response.status_code == 409
    assert fake_asaas.requests == []


async def test_cancel_while_subscription_is_still_being_confirmed(client: AsyncClient, db_session, fake_asaas):
    email = "pending-confirm@example.com"
    headers = await _register(client, email)
    user = await _user(db_session, email)
    row = await _sub(db_session, user.id)
    row.plan_name, row.status = "pro", "active"  # CHECKOUT_PAID chegou, SUBSCRIPTION_CREATED ainda não
    await db_session.commit()

    response = await client.post("/api/v1/subscriptions/cancel", headers=headers)

    assert response.status_code == 409
    assert "confirmada" in response.json()["detail"]
    assert fake_asaas.requests == []
