"""
Regra de negócio das assinaturas via Asaas: iniciar checkout, cancelar e processar webhooks.

Princípios:
* O backend define plano, valor e URLs de retorno. O frontend envia o plano e os dados cadastrais do pagador.
* Pagamento só é considerado confirmado por evento de webhook do Asaas, nunca pela página de sucesso.
* Todo evento é processado uma única vez (idempotência pelo ``id`` do evento).
* Eventos atrasados de pagamento nunca reativam uma assinatura já cancelada.
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.documents import is_valid_cpf_cnpj, normalize_document
from app.core.plan_catalog import PLANS, get_plan
from app.core.plans import get_user_plan
from app.models.asaas import AsaasCheckout, AsaasWebhookEvent
from app.models.subscription import Subscription
from app.models.user import User
from app.services import asaas_client

logger = logging.getLogger("app.services.asaas")

BRT = timezone(timedelta(hours=-3))
# Estados em que a assinatura ainda existe no Asaas e pode gerar novas cobranças.
LIVE_STATUSES = {"active", "trialing", "past_due"}


class CheckoutError(Exception):
    """Erro de regra de negócio; ``message`` é seguro para mostrar ao usuário."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


# ── Helpers ──────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    """SQLite devolve datas sem fuso; trata como UTC para poder comparar."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _add_one_month(value: datetime) -> datetime:
    month_index = value.month  # 1..12 -> mês seguinte
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _parse_date(value: str | None) -> datetime | None:
    """Converte 'YYYY-MM-DD' (formato das datas do webhook) em datetime UTC."""
    if not value:
        return None
    try:
        parsed = date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
    return datetime(parsed.year, parsed.month, parsed.day, tzinfo=timezone.utc)


async def _get_subscription_row(db: AsyncSession, user_id) -> Subscription:
    """Linha de assinatura do usuário (todo usuário recebe uma 'free' no cadastro)."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id).order_by(Subscription.created_at.desc())
    )
    row = result.scalars().first()
    if row is None:
        row = Subscription(user_id=user_id, plan_name="free", status="active")
        db.add(row)
        await db.flush()
    return row


def _return_urls() -> tuple[str, str, str]:
    base = settings.FRONTEND_URL.rstrip("/")
    page = f"{base}/settings/billing"
    return f"{page}?success=true", f"{page}?canceled=true", f"{page}?expired=true"


# ── Iniciar checkout ─────────────────────────────────────────


async def start_checkout(
    db: AsyncSession, user: User, plan_name: str, *, cpf_cnpj: str | None,
    phone: str | None, address: str | None, address_number: str | None,
    postal_code: str | None, province: str | None, city: str | None,
) -> str:
    """Cria (ou reaproveita) um checkout hospedado do Asaas e devolve o link."""
    plan = get_plan(plan_name)
    if plan is None or not plan.purchasable:
        raise CheckoutError(400, "Este plano não está disponível para contratação.")

    # Não permite assinar de novo enquanto já houver assinatura (evita cobrança duplicada).
    row = await _get_subscription_row(db, user.id)
    if await get_user_plan(db, user.id) != "free" or (
        row.asaas_subscription_id and row.status in LIVE_STATUSES | {"incomplete"}
    ):
        raise CheckoutError(409, "Você já tem uma assinatura ou pagamento Pix pendente. Cancele-o antes de contratar novamente.")

    # Reaproveita um checkout ainda válido (evita criar vários para o mesmo pedido).
    pending = await db.execute(
        select(AsaasCheckout)
        .where(AsaasCheckout.user_id == user.id, AsaasCheckout.plan_name == plan.name, AsaasCheckout.status == "ACTIVE")
        .order_by(AsaasCheckout.created_at.desc())
    )
    existing = pending.scalars().first()
    if existing and existing.expires_at and _aware(existing.expires_at) > _now() + timedelta(minutes=2):
        return existing.link

    customer_id = await _ensure_customer(
        db, user, cpf_cnpj=cpf_cnpj, phone=phone, address=address,
        address_number=address_number, postal_code=postal_code, province=province, city=city,
    )

    success_url, cancel_url, expired_url = _return_urls()
    minutes = max(10, min(1440, settings.ASAAS_CHECKOUT_MINUTES_TO_EXPIRE))
    try:
        checkout_id, link = await asaas_client.create_checkout(
            customer_id=customer_id,
            item_name=f"Texas CRM — Plano {plan.display_name}",
            item_description=f"Assinatura mensal do plano {plan.display_name}",
            value=plan.price_monthly,
            next_due_date=datetime.now(BRT).strftime("%Y-%m-%d %H:%M:%S"),
            success_url=success_url,
            cancel_url=cancel_url,
            expired_url=expired_url,
            minutes_to_expire=minutes,
            external_reference=f"user:{user.id}:plan:{plan.name}",
        )
    except asaas_client.AsaasError as exc:
        raise CheckoutError(502 if exc.status_code is None or exc.status_code >= 500 else 400, exc.message) from exc

    db.add(
        AsaasCheckout(
            user_id=user.id,
            checkout_id=checkout_id,
            plan_name=plan.name,
            status="ACTIVE",
            link=link,
            expires_at=_now() + timedelta(minutes=minutes),
        )
    )
    await db.flush()
    logger.info("Checkout %s criado para o usuário %s (plano %s)", checkout_id, user.id, plan.name)
    return link


async def _ensure_customer(
    db: AsyncSession, user: User, *, cpf_cnpj: str | None, phone: str | None,
    address: str | None, address_number: str | None, postal_code: str | None,
    province: str | None, city: str | None,
) -> str:
    """Cria ou atualiza o cadastro do cliente no Asaas antes de abrir o checkout."""
    required = {
        "CPF/CNPJ": cpf_cnpj, "telefone": phone, "endereço": address,
        "número do endereço": address_number, "CEP": postal_code,
        "bairro": province, "cidade": city,
    }
    if not cpf_cnpj or not is_valid_cpf_cnpj(cpf_cnpj):
        raise CheckoutError(400, "Informe um CPF ou CNPJ válido para continuar.")
    missing = [label for label, value in required.items() if not value or not value.strip()]
    if missing:
        raise CheckoutError(400, "Preencha os dados obrigatórios para pagamento: " + ", ".join(missing) + ".")

    clean_phone = "".join(ch for ch in phone if ch.isdigit())
    clean_postal_code = "".join(ch for ch in postal_code if ch.isdigit())
    if len(clean_phone) not in (10, 11):
        raise CheckoutError(400, "Informe um telefone com DDD válido.")
    if len(clean_postal_code) != 8:
        raise CheckoutError(400, "Informe um CEP válido com 8 dígitos.")
    if not city.strip().isdigit() or len(city.strip()) != 7:
        raise CheckoutError(400, "Não foi possível identificar o código IBGE da cidade pelo CEP. Confira o CEP informado.")

    customer_data = {
        "name": user.full_name or user.email.split("@")[0], "email": user.email,
        "cpf_cnpj": normalize_document(cpf_cnpj), "phone": clean_phone,
        "address": address.strip(), "address_number": address_number.strip(),
        "postal_code": clean_postal_code, "province": province.strip(),
    }
    try:
        customer_id = user.asaas_customer_id
        if not customer_id:
            customer_id = await asaas_client.find_customer_by_external_reference(str(user.id))
        if customer_id:
            await asaas_client.update_customer(customer_id, **customer_data)
        else:
            customer_id = await asaas_client.create_customer(**customer_data, external_reference=str(user.id))
    except asaas_client.AsaasError as exc:
        raise CheckoutError(502 if exc.status_code is None or exc.status_code >= 500 else 400, exc.message) from exc

    if user.asaas_customer_id != customer_id:
        user.asaas_customer_id = customer_id
    await db.commit()
    return customer_id


# ── Cancelar assinatura ──────────────────────────────────────


async def cancel_subscription(db: AsyncSession, user: User) -> Subscription:
    """Cancela a recorrência no Asaas. O acesso segue até o fim do período já pago."""
    row = await _get_subscription_row(db, user.id)
    if row.status == "canceled" or row.plan_name == "free":
        raise CheckoutError(409, "Você não tem uma assinatura ativa para cancelar.")
    if not row.asaas_subscription_id:
        raise CheckoutError(409, "Sua assinatura ainda está sendo confirmada. Tente novamente em alguns minutos.")

    try:
        await asaas_client.delete_subscription(row.asaas_subscription_id)
    except asaas_client.AsaasError as exc:
        raise CheckoutError(502 if exc.status_code is None or exc.status_code >= 500 else 400, exc.message) from exc

    _mark_canceled(row)
    await db.flush()
    logger.info("Assinatura %s cancelada pelo usuário %s", row.asaas_subscription_id, user.id)
    return row


def _mark_canceled(row: Subscription) -> None:
    """Marca como cancelada. Mantém o plano enquanto houver período pago pela frente."""
    row.status = "canceled"
    end = _aware(row.current_period_end)
    if end is None or end <= _now():
        row.plan_name = "free"


# ── Webhooks ─────────────────────────────────────────────────


async def handle_webhook(db: AsyncSession, payload: dict) -> str:
    """Processa um evento do Asaas. Devolve ``processed``, ``ignored`` ou ``duplicate``.

    Deve rodar numa transação: o registro do evento e as alterações são confirmados juntos, então
    uma falha no meio desfaz tudo e o Asaas reenvia o evento.
    """
    event_id = payload.get("id")
    event = payload.get("event")
    if not event_id or not event:
        return "ignored"

    seen = await db.execute(select(AsaasWebhookEvent.id).where(AsaasWebhookEvent.event_id == event_id))
    if seen.first() is not None:
        return "duplicate"
    db.add(AsaasWebhookEvent(event_id=event_id, event_type=event))
    await db.flush()  # violação de unicidade aqui = entrega concorrente do mesmo evento

    if event.startswith("CHECKOUT_"):
        await _on_checkout_event(db, event, payload.get("checkout") or {})
    elif event.startswith("SUBSCRIPTION_"):
        await _on_subscription_event(db, event, payload.get("subscription") or {})
    elif event.startswith("PAYMENT_"):
        await _on_payment_event(db, event, payload.get("payment") or {})
    else:
        logger.info("Evento do Asaas não tratado: %s", event)
        return "ignored"
    return "processed"


async def _on_checkout_event(db: AsyncSession, event: str, checkout: dict) -> None:
    checkout_id = checkout.get("id")
    result = await db.execute(select(AsaasCheckout).where(AsaasCheckout.checkout_id == checkout_id))
    record = result.scalar_one_or_none()
    if record is None:
        logger.warning("%s para checkout desconhecido: %s", event, checkout_id)
        return

    if event == "CHECKOUT_PAID":
        record.status = "PAID"
        user = await db.get(User, record.user_id)
        if user is None:
            return
        customer = checkout.get("customer")
        if customer and not user.asaas_customer_id:
            user.asaas_customer_id = customer
        row = await _get_subscription_row(db, user.id)
        row.plan_name = record.plan_name
        row.status = "active"
        now = _now()
        row.current_period_start = now
        # Provisório: o próximo vencimento exato chega nos eventos da assinatura/cobrança.
        row.current_period_end = _add_one_month(now)
        logger.info("Checkout %s pago: usuário %s no plano %s", checkout_id, user.id, record.plan_name)
    elif event == "CHECKOUT_CANCELED":
        record.status = "CANCELED"
    elif event == "CHECKOUT_EXPIRED":
        record.status = "EXPIRED"


async def _row_for_asaas_ids(
    db: AsyncSession, subscription_id: str | None, customer_id: str | None, *, adopt: bool
) -> Subscription | None:
    """Localiza a linha de assinatura pelo id da assinatura no Asaas, ou pelo cliente.

    Com ``adopt``, grava o id da assinatura numa linha que ainda não tinha um (o evento de
    cobrança pode chegar antes do de assinatura).
    """
    if subscription_id:
        result = await db.execute(select(Subscription).where(Subscription.asaas_subscription_id == subscription_id))
        row = result.scalar_one_or_none()
        if row is not None:
            return row
    if not customer_id:
        return None
    result = await db.execute(select(User).where(User.asaas_customer_id == customer_id))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    row = await _get_subscription_row(db, user.id)
    if subscription_id and row.asaas_subscription_id is None and adopt:
        row.asaas_subscription_id = subscription_id
        return row
    # A linha já aponta para outra assinatura (antiga): este evento é de uma assinatura que não vale mais.
    return row if not subscription_id or row.asaas_subscription_id == subscription_id else None


async def _on_subscription_event(db: AsyncSession, event: str, sub: dict) -> None:
    sub_id, customer_id = sub.get("id"), sub.get("customer")
    if not sub_id:
        return

    if event == "SUBSCRIPTION_CREATED":
        result = await db.execute(select(User).where(User.asaas_customer_id == customer_id))
        user = result.scalar_one_or_none()
        if user is None:
            logger.warning("SUBSCRIPTION_CREATED de cliente desconhecido: %s", customer_id)
            return
        row = await _get_subscription_row(db, user.id)
        row.asaas_subscription_id = sub_id  # a assinatura nova substitui qualquer id antigo
        return

    row = await _row_for_asaas_ids(db, sub_id, customer_id, adopt=False)
    if row is None or row.asaas_subscription_id != sub_id:
        logger.warning("%s para assinatura desconhecida: %s", event, sub_id)
        return

    if event in ("SUBSCRIPTION_INACTIVATED", "SUBSCRIPTION_DELETED"):
        _mark_canceled(row)
    elif event == "SUBSCRIPTION_UPDATED":
        if sub.get("status") in ("INACTIVE", "EXPIRED"):
            _mark_canceled(row)
        elif row.status != "canceled":
            next_due = _parse_date(sub.get("nextDueDate"))
            if next_due:
                row.current_period_end = next_due


def _plan_from_value(value) -> str | None:
    """Descobre o plano pago pelo valor da cobrança (usado só se o checkout ainda não foi processado)."""
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:  # noqa: BLE001
        return None
    for plan in PLANS.values():
        if plan.purchasable and plan.price_monthly == amount:
            return plan.name
    return None


async def _on_payment_event(db: AsyncSession, event: str, payment: dict) -> None:
    subscription_id = payment.get("subscription")
    if not subscription_id:
        return  # cobrança avulsa: não é do fluxo de assinatura

    row = await _row_for_asaas_ids(db, subscription_id, payment.get("customer"), adopt=True)
    if row is None or row.asaas_subscription_id != subscription_id:
        logger.warning("%s para assinatura desconhecida: %s", event, subscription_id)
        return
    if row.status == "canceled":
        # Cobrança atrasada de uma assinatura já cancelada: não pode reativar o acesso.
        logger.info("%s ignorado: assinatura %s já cancelada", event, subscription_id)
        return

    if event in ("PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"):
        plan = row.plan_name if row.plan_name != "free" else _plan_from_value(payment.get("value"))
        if plan is None:
            logger.warning("Não foi possível determinar o plano da cobrança %s", payment.get("id"))
            return
        row.plan_name = plan
        row.status = "active"
        paid_on = _parse_date(payment.get("confirmedDate") or payment.get("paymentDate")) or _now()
        row.current_period_start = paid_on
        due = _parse_date(payment.get("dueDate")) or paid_on
        new_end = _add_one_month(max(due, paid_on))
        current_end = _aware(row.current_period_end)
        if current_end is None or new_end > current_end:
            row.current_period_end = new_end
    elif event in ("PAYMENT_OVERDUE", "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED", "PAYMENT_CHARGEBACK_REQUESTED"):
        row.status = "past_due"
    elif event == "PAYMENT_REFUNDED":
        row.status = "canceled"
        row.plan_name = "free"
        row.current_period_end = _now()


async def start_pix_subscription(
    db: AsyncSession, user: User, plan_name: str, *, cpf_cnpj: str | None,
    phone: str | None, address: str | None, address_number: str | None,
    postal_code: str | None, province: str | None, city: str | None,
) -> dict:
    """Cria ou recupera uma assinatura mensal de Pix convencional e retorna o QR Code inicial."""
    plan = get_plan(plan_name)
    if plan is None or not plan.purchasable:
        raise CheckoutError(400, "Este plano não está disponível para contratação.")

    row = await _get_subscription_row(db, user.id)
    if await get_user_plan(db, user.id) != "free" or (
        row.asaas_subscription_id and row.status in LIVE_STATUSES
    ):
        raise CheckoutError(409, "Você já tem uma assinatura. Cancele-a antes de contratar novamente.")
    if row.status == "incomplete" and row.asaas_subscription_id and row.plan_name != plan.name:
        raise CheckoutError(409, "Você já tem um pagamento Pix pendente para outro plano. Cancele-o antes de continuar.")

    # Reutiliza uma assinatura incompleta se a primeira resposta não chegou ao navegador.
    subscription_id = None
    if row.status == "incomplete" and row.plan_name == plan.name and row.asaas_subscription_id:
        subscription_id = row.asaas_subscription_id
    else:
        customer_id = await _ensure_customer(
            db, user, cpf_cnpj=cpf_cnpj, phone=phone, address=address,
            address_number=address_number, postal_code=postal_code, province=province, city=city,
        )
        try:
            subscription_id = await asaas_client.create_pix_subscription(
                customer_id=customer_id,
                value=plan.price_monthly,
                next_due_date=datetime.now(BRT).strftime("%Y-%m-%d"),
                description=f"Assinatura mensal TexasCRM — Plano {plan.display_name}",
                external_reference=f"user:{user.id}:plan:{plan.name}:pix",
            )
        except asaas_client.AsaasError as exc:
            raise CheckoutError(502 if exc.status_code is None or exc.status_code >= 500 else 400, exc.message) from exc

        # Persiste o vínculo antes de buscar o QR: um retry não cria outra assinatura.
        row.asaas_subscription_id = subscription_id
        row.plan_name = plan.name
        row.status = "incomplete"
        row.current_period_start = None
        row.current_period_end = None
        await db.commit()

    try:
        payments = await asaas_client.list_subscription_payments(subscription_id)
        if not payments:
            raise CheckoutError(409, "A cobrança Pix está sendo gerada pelo Asaas. Aguarde alguns instantes e tente novamente.")
        payment = next(
            (item for item in payments if item.get("status") not in {"DELETED", "REFUNDED"}),
            payments[0],
        )
        qr = await asaas_client.get_pix_qr_code(payment["id"])
    except asaas_client.AsaasError as exc:
        raise CheckoutError(502 if exc.status_code is None or exc.status_code >= 500 else 400, exc.message) from exc

    return {
        "subscription_id": subscription_id,
        "payment_id": payment["id"],
        "encoded_image": qr.get("encodedImage"),
        "payload": qr.get("payload"),
        "expiration_date": qr.get("expirationDate"),
        "value": float(payment.get("value") or plan.price_monthly),
    }
