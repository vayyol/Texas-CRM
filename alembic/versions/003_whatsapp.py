"""Tabelas iniciais da central WhatsApp.

Revision ID: 003
Revises: 002
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_consents",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("terms_version", sa.String(30), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_whatsapp_consents_user_id"),
    )
    op.create_table(
        "whatsapp_sessions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("session_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="STOPPED"),
        sa.Column("phone_number", sa.String(30), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_whatsapp_sessions_user_id"),
        sa.UniqueConstraint("session_name", name="uq_whatsapp_sessions_session_name"),
    )
    op.create_index("ix_whatsapp_sessions_user_id", "whatsapp_sessions", ["user_id"])
    op.create_table(
        "whatsapp_conversations",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("chat_id", sa.String(255), nullable=False),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(30), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_preview", sa.String(500), nullable=True),
        sa.Column("unread_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["whatsapp_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "chat_id", name="uq_whatsapp_conversation_session_chat"),
    )
    op.create_index("ix_whatsapp_conversations_user_id", "whatsapp_conversations", ["user_id"])
    op.create_index("ix_whatsapp_conversations_session_id", "whatsapp_conversations", ["session_id"])
    op.create_table(
        "whatsapp_messages",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("waha_message_id", sa.String(255), nullable=True),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(30), nullable=False, server_default="text"),
        sa.Column("status", sa.String(30), nullable=False, server_default="received"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["whatsapp_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("waha_message_id", name="uq_whatsapp_messages_waha_message_id"),
    )
    op.create_index("ix_whatsapp_messages_user_id", "whatsapp_messages", ["user_id"])
    op.create_index("ix_whatsapp_messages_conversation_id", "whatsapp_messages", ["conversation_id"])
    op.create_index("ix_whatsapp_messages_user_created", "whatsapp_messages", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("whatsapp_messages")
    op.drop_table("whatsapp_conversations")
    op.drop_index("ix_whatsapp_sessions_user_id", table_name="whatsapp_sessions")
    op.drop_table("whatsapp_sessions")
    op.drop_table("whatsapp_consents")
