"""add tool_calls column to messages

Revision ID: tool_calls_v1
Revises: search_settings_v1
Create Date: 2026-03-02 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "tool_calls_v1"
down_revision: Union[str, Sequence[str], None] = "search_settings_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "tool_calls",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Extracted tool call data for frontend rendering",
        ),
    )


def downgrade() -> None:
    op.drop_column("messages", "tool_calls")
