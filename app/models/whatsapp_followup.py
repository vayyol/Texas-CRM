"""Configurações e histórico dos follow-ups enviados pelo WhatsApp."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WhatsAppFollowupSetting(Base):
    __tablename__ = "whatsapp_followup_settings"
    __table_args__ = (UniqueConstraint("user_id", "followup_type", name="uq_whatsapp_followup_setting_user_type"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    followup_type: Mapped[str] = mapped_column(String(40), nullable=False)
    auto_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message_template: Mapped[str] = mapped_column(Text, nullable=False)


class WhatsAppFollowupRecord(Base):
    __tablename__ = "whatsapp_followup_records"
    __table_args__ = (
        UniqueConstraint("user_id", "event_key", name="uq_whatsapp_followup_record_user_event"),
        Index("ix_whatsapp_followup_records_user_status", "user_id", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_key: Mapped[str] = mapped_column(String(255), nullable=False)
    followup_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    client_id: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    auto_send_pending: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class WhatsAppFollowupCursor(Base):
    __tablename__ = "whatsapp_followup_cursors"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    last_scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    initialized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
