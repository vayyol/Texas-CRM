"""Persistência de configurações e registros de follow-up WhatsApp.

Revision ID: 004
Revises: 003
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_followup_settings",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("followup_type", sa.String(40), nullable=False),
        sa.Column("auto_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("auto_enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_template", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "followup_type", name="uq_whatsapp_followup_setting_user_type"),
    )
    op.create_index("ix_whatsapp_followup_settings_user_id", "whatsapp_followup_settings", ["user_id"])

    op.create_table(
        "whatsapp_followup_records",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("event_key", sa.String(255), nullable=False),
        sa.Column("followup_type", sa.String(40), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("auto_send_pending", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "event_key", name="uq_whatsapp_followup_record_user_event"),
    )
    op.create_index("ix_whatsapp_followup_records_user_id", "whatsapp_followup_records", ["user_id"])
    op.create_index("ix_whatsapp_followup_records_followup_type", "whatsapp_followup_records", ["followup_type"])
    op.create_index("ix_whatsapp_followup_records_user_status", "whatsapp_followup_records", ["user_id", "status"])

    op.create_table(
        "whatsapp_followup_cursors",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("initialized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_whatsapp_followup_cursors_user_id"),
    )


def downgrade() -> None:
    op.drop_table("whatsapp_followup_cursors")
    op.drop_table("whatsapp_followup_records")
    op.drop_table("whatsapp_followup_settings")
