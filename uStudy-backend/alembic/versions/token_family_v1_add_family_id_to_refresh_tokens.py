"""Add family_id to refresh_tokens for multi-device support

Revision ID: token_family_v1
Revises: expand_node_v2
Create Date: 2026-03-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "token_family_v1"
down_revision: Union[str, None] = "expand_node_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add nullable family_id column
    op.add_column(
        "refresh_tokens",
        sa.Column("family_id", UUID(as_uuid=True), nullable=True),
    )

    # Backfill: each existing token becomes its own family root
    op.execute("UPDATE refresh_tokens SET family_id = id WHERE family_id IS NULL")

    # Create index for efficient family lookups
    op.create_index(
        "ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "family_id")
