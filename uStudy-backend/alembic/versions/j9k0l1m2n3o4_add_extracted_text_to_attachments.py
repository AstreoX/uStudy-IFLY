"""add extracted_text to message_attachments

Revision ID: j9k0l1m2n3o4
Revises: i8j9k0l1m2n3
Create Date: 2026-02-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "j9k0l1m2n3o4"
down_revision: Union[str, None] = "i8j9k0l1m2n3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add extracted_text column for caching extracted file content
    op.add_column(
        "message_attachments",
        sa.Column("extracted_text", sa.Text(), nullable=True),
    )

    # Add extraction_metadata column for storing extraction info
    # Format: {
    #   "extracted_at": "ISO timestamp",
    #   "token_count": int,
    #   "truncated": bool,
    #   "extraction_error": str | None
    # }
    op.add_column(
        "message_attachments",
        sa.Column(
            "extraction_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("message_attachments", "extraction_metadata")
    op.drop_column("message_attachments", "extracted_text")
