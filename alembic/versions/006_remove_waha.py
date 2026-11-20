"""Remove WAHA provider metadata and generalize message identifier."""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.drop_column("whatsapp_sessions", "provider")
    op.drop_constraint("uq_whatsapp_messages_waha_message_id", "whatsapp_messages", type_="unique")
    op.alter_column("whatsapp_messages", "waha_message_id", new_column_name="provider_message_id")
    op.create_unique_constraint("uq_whatsapp_messages_provider_message_id", "whatsapp_messages", ["provider_message_id"])

def downgrade() -> None:
    op.drop_constraint("uq_whatsapp_messages_provider_message_id", "whatsapp_messages", type_="unique")
    op.alter_column("whatsapp_messages", "provider_message_id", new_column_name="waha_message_id")
    op.create_unique_constraint("uq_whatsapp_messages_waha_message_id", "whatsapp_messages", ["waha_message_id"])
    op.add_column("whatsapp_sessions", sa.Column("provider", sa.String(20), nullable=False, server_default="uazapi"))
