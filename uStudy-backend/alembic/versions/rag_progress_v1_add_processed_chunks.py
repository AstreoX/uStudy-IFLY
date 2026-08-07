"""Add processed_chunks to document_processing_tasks for progress tracking.

Revision ID: rag_progress_v1
Revises: activation_tier_v1
Create Date: 2026-03-16
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "rag_progress_v1"
down_revision: Union[str, None] = "activation_tier_v1"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "document_processing_tasks",
        sa.Column("processed_chunks", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("document_processing_tasks", "processed_chunks")
