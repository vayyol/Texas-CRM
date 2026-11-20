"""Campos de integração UazapiGO.
Revision ID: 005
Revises: 004
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("whatsapp_sessions", sa.Column("provider", sa.String(20), nullable=False, server_default="waha"))
    op.add_column("whatsapp_sessions", sa.Column("provider_token_encrypted", sa.Text(), nullable=True))
    op.add_column("whatsapp_sessions", sa.Column("provider_instance_id", sa.String(120), nullable=True))
    op.add_column("whatsapp_sessions", sa.Column("qr_data", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("whatsapp_sessions", "qr_data")
    op.drop_column("whatsapp_sessions", "provider_instance_id")
    op.drop_column("whatsapp_sessions", "provider_token_encrypted")
    op.drop_column("whatsapp_sessions", "provider")
