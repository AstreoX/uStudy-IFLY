"""add space_memories table

Revision ID: e4f5g6h7i8j9
Revises: d3e4f5g6h7i8
Create Date: 2025-02-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4f5g6h7i8j9"
down_revision: Union[str, None] = "d3e4f5g6h7i8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "space_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "space_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("spaces.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "entries",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("next_entry_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_space_memories_space_id",
        "space_memories",
        ["space_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_space_memories_space_id")
    op.drop_table("space_memories")
