"""Integração com o Asaas: colunas de vínculo e tabelas de apoio.

Migration somente ADITIVA: não remove nem altera nada da integração antiga (Stripe).
As colunas stripe_customer_id e stripe_subscription_id continuam existindo.

Revision ID: 002
Revises: 001
Create Date: 2026-11-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Colunas de vínculo (nullable, sem impacto nos dados existentes) ──
    op.add_column("users", sa.Column("asaas_customer_id", sa.String(255), nullable=True))
    op.create_index("ix_users_asaas_customer_id", "users", ["asaas_customer_id"], unique=True)

    op.add_column("subscriptions", sa.Column("asaas_subscription_id", sa.String(255), nullable=True))
    op.create_index(
        "ix_subscriptions_asaas_subscription_id", "subscriptions", ["asaas_subscription_id"], unique=True
    )

    # ── Checkouts hospedados criados no Asaas ──
    op.create_table(
        "asaas_checkouts",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("checkout_id", sa.String(100), nullable=False),
        sa.Column("plan_name", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("link", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_asaas_checkouts_user_id", "asaas_checkouts", ["user_id"])
    op.create_index("ix_asaas_checkouts_checkout_id", "asaas_checkouts", ["checkout_id"], unique=True)

    # ── Eventos de webhook já processados (idempotência) ──
    op.create_table(
        "asaas_webhook_events",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asaas_webhook_events_event_id", "asaas_webhook_events", ["event_id"], unique=True)


def downgrade() -> None:
    op.drop_table("asaas_webhook_events")
    op.drop_table("asaas_checkouts")
    op.drop_index("ix_subscriptions_asaas_subscription_id", table_name="subscriptions")
    op.drop_column("subscriptions", "asaas_subscription_id")
    op.drop_index("ix_users_asaas_customer_id", table_name="users")
    op.drop_column("users", "asaas_customer_id")
