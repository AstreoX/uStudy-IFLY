"""add daily_study_records table

Revision ID: daily_study_v1
Revises: mem_sharing_v1
Create Date: 2026-02-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "daily_study_v1"
down_revision: Union[str, None] = "mem_sharing_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create daily_study_records table."""
    op.create_table(
        "daily_study_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("study_date", sa.Date(), nullable=False),
        sa.Column("activity_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "study_date", name="uq_dsr_user_study_date"),
    )
    op.create_index("ix_dsr_user_date", "daily_study_records", ["user_id", "study_date"])


def downgrade() -> None:
    """Drop daily_study_records table."""
    op.drop_index("ix_dsr_user_date", table_name="daily_study_records")
    op.drop_table("daily_study_records")
