"""add response_status to messages

Revision ID: message_response_status_v1
Revises: tool_calls_v1
Create Date: 2026-03-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "message_response_status_v1"
down_revision: Union[str, Sequence[str], None] = "tool_calls_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


response_status_enum = postgresql.ENUM(
    "completed",
    "stopped",
    name="messageresponsestatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    response_status_enum.create(bind, checkfirst=True)
    op.add_column(
        "messages",
        sa.Column(
            "response_status",
            response_status_enum,
            nullable=False,
            server_default="completed",
            comment="Assistant response generation status",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_column("messages", "response_status")
    response_status_enum.drop(bind, checkfirst=True)
