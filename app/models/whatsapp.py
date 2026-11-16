"""Modelos isolados da central de WhatsApp."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WhatsAppConsent(Base):
    __tablename__ = "whatsapp_consents"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    terms_version: Mapped[str] = mapped_column(String(30), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)


class WhatsAppSession(Base):
    __tablename__ = "whatsapp_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    session_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="STOPPED", nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WhatsAppConversation(Base):
    __tablename__ = "whatsapp_conversations"
    __table_args__ = (UniqueConstraint("session_id", "chat_id", name="uq_whatsapp_conversation_session_chat"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("whatsapp_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_preview: Mapped[str | None] = mapped_column(String(500), nullable=True)
    unread_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"
    __table_args__ = (Index("ix_whatsapp_messages_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("whatsapp_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    waha_message_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), default="text", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="received", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
