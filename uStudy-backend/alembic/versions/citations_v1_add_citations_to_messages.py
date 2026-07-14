"""add citations column to messages

Revision ID: citations_v1
Revises: hybrid_search_v1
Create Date: 2026-03-14 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "citations_v1"
down_revision: Union[str, None] = "hybrid_search_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "citations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Structured citation metadata for source attribution",
        ),
    )


def downgrade() -> None:
    op.drop_column("messages", "citations")
