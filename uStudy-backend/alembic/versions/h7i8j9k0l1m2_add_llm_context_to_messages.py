"""add llm_context to messages

Revision ID: h7i8j9k0l1m2
Revises: g6h7i8j9k0l1
Create Date: 2026-02-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h7i8j9k0l1m2"
down_revision: Union[str, None] = "g6h7i8j9k0l1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add llm_context column to messages table
    op.add_column(
        "messages",
        sa.Column(
            "llm_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Complete LLM API request/response context for debugging and feedback",
        ),
    )


def downgrade() -> None:
    op.drop_column("messages", "llm_context")
