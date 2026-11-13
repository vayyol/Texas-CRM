"""
Subscription routes: plans, Asaas hosted checkout, cancellation, and Asaas webhooks.

A integração antiga da Stripe foi substituída aqui; ``app/services/stripe_service.py`` continua no
repositório (sem uso) enquanto a transição não termina.
"""

from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import get_current_active_user
from app.core.plan_catalog import list_plans
from app.database import get_db
from app.models.subscription import Subscription
from app.schemas.subscription import (
    CancelResponse,
    CheckoutRequest,
    CheckoutResponse,
    PlanResponse,
    SubscriptionResponse,
)
from app.services import asaas_service

logger = logging.getLogger("app.api.subscriptions")

router = APIRouter()


@router.get(
    "/plans",
    response_model=list[PlanResponse],
    summary="List available plans",
)
async def get_plans():
    """Return all available subscription plans with features."""
    return list_plans()


@router.get(
    "/current",
    response_model=SubscriptionResponse | None,
    summary="Get current subscription",
)
async def get_current_subscription(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's subscription (``null`` if none)."""
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == current_user.id).order_by(Subscription.created_at.desc())
    )
    return result.scalars().first()


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    summary="Create hosted checkout (Asaas)",
)
async def create_checkout(
    body: CheckoutRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Cria o checkout hospedado do Asaas para o plano pedido e devolve o link.

    O valor e as URLs de retorno são definidos pelo backend; o frontend envia só o plano.
    """
    try:
        link = await asaas_service.start_checkout(db, current_user, body.plan, body.cpf_cnpj)
    except asaas_service.CheckoutError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return CheckoutResponse(checkout_url=link)


@router.post(
    "/cancel",
    response_model=CancelResponse,
    summary="Cancel the current subscription",
)
async def cancel_subscription(
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancela a recorrência. O acesso continua até o fim do período já pago."""
    try:
        row = await asaas_service.cancel_subscription(db, current_user)
    except asaas_service.CheckoutError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    access_until = row.current_period_end if row.plan_name != "free" else None
    return CancelResponse(status=row.status, access_until=access_until)


@router.post("/webhook/asaas", summary="Asaas webhook endpoint")
async def asaas_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Recebe os eventos do Asaas (checkout, assinatura e cobrança).

    Autentica pelo header ``asaas-access-token`` (token próprio do webhook, nunca a chave da API),
    processa cada evento uma única vez e só confirma (HTTP 200) depois de gravar o resultado.
    """
    expected = settings.ASAAS_WEBHOOK_TOKEN.get_secret_value()
    if not expected:
        # Falha fechada: sem token configurado não aceitamos evento nenhum.
        logger.error("ASAAS_WEBHOOK_TOKEN não configurado: webhook recusado.")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook não configurado")

    received = request.headers.get("asaas-access-token", "")
    if not hmac.compare_digest(received.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload inválido")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload inválido")

    try:
        result = await asaas_service.handle_webhook(db, payload)
        await db.commit()
    except IntegrityError:
        # Mesma entrega chegando em paralelo: o outro processamento já cuidou do evento.
        await db.rollback()
        return {"status": "duplicate"}
    except Exception:
        # Desfaz tudo (inclusive o registro do evento) e responde erro para o Asaas reenviar.
        await db.rollback()
        logger.exception("Falha ao processar o evento %s do Asaas", payload.get("id"))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro ao processar o evento")

    return {"status": result}
