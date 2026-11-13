"""
Modelos de apoio à integração com o Asaas.

* ``AsaasCheckout``: cada checkout hospedado criado para um usuário. O payload do webhook de checkout
  traz apenas ``checkout.id`` (sem ``externalReference``), então este registro é o vínculo
  confiável entre o checkout e o usuário do Texas CRM.
* ``AsaasWebhookEvent``: eventos de webhook já processados (o Asaas entrega *at least once*, então o
  mesmo evento pode chegar mais de uma vez; o ``id`` do evento garante a idempotência).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AsaasCheckout(Base):
    __tablename__ = "asaas_checkouts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    checkout_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    plan_name: Mapped[str] = mapped_column(String(50), nullable=False)
    # ACTIVE | PAID | CANCELED | EXPIRED (mesmos estados do Asaas)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    link: Mapped[str] = mapped_column(String(500), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<AsaasCheckout {self.checkout_id} {self.status}>"


class AsaasWebhookEvent(Base):
    __tablename__ = "asaas_webhook_events"

    event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)

    def __repr__(self) -> str:
        return f"<AsaasWebhookEvent {self.event_type} {self.event_id}>"
