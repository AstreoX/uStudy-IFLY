"""Add resumable presentation run state.

Revision ID: teacher_presentation_recovery_v1
Revises: teacher_presentations_v1
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "teacher_presentation_recovery_v1"
down_revision: str | None = "teacher_presentations_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE presentationrunstatus ADD VALUE IF NOT EXISTS 'recovering'")
    op.add_column(
        "teacher_presentation_runs",
        sa.Column("attempt_count", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "teacher_presentation_runs",
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "teacher_presentation_runs",
        sa.Column("retry_deadline_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("teacher_presentation_runs", "retry_deadline_at")
    op.drop_column("teacher_presentation_runs", "last_heartbeat_at")
    op.drop_column("teacher_presentation_runs", "attempt_count")
    # PostgreSQL enum values are intentionally retained on downgrade.
