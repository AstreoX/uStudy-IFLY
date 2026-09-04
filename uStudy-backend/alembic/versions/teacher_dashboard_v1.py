"""add teacher dashboard role and mastery history

Revision ID: teacher_dashboard_v1
Revises: remove_quick_chat_v1
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "teacher_dashboard_v1"
down_revision: Union[str, None] = "remove_quick_chat_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # spacememberrole explicitly stores enum values (lowercase), unlike most
    # legacy SQLAlchemy enums in this project.
    op.execute("ALTER TYPE spacememberrole ADD VALUE IF NOT EXISTS 'teacher'")

    op.create_table(
        "node_mastery_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_mastery", sa.Integer(), nullable=True),
        sa.Column("new_mastery", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "previous_mastery IS NULL OR (previous_mastery >= 0 AND previous_mastery <= 100)",
            name="ck_mastery_events_previous_range",
        ),
        sa.CheckConstraint(
            "new_mastery >= 0 AND new_mastery <= 100",
            name="ck_mastery_events_new_range",
        ),
        sa.CheckConstraint(
            "source IN ('baseline', 'chat_tool', 'quiz_evaluation')",
            name="ck_mastery_events_source",
        ),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mastery_events_space_time",
        "node_mastery_events",
        ["space_id", "created_at"],
    )
    op.create_index(
        "ix_mastery_events_user_time",
        "node_mastery_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_mastery_events_user_node_time",
        "node_mastery_events",
        ["user_id", "node_id", "created_at"],
    )
    op.create_index(
        "ix_study_activity_space_time",
        "study_activity_logs",
        ["space_id", "activity_time"],
    )

    # The migration timestamp is the trustworthy start of history. Existing
    # current values become a baseline, not fabricated historical changes.
    op.execute(
        """
        INSERT INTO node_mastery_events (
            id, space_id, node_id, user_id, previous_mastery,
            new_mastery, source, reason, created_at
        )
        SELECT gen_random_uuid(), n.space_id, num.node_id, num.user_id, NULL,
               num.mastery, 'baseline', NULL, now()
        FROM node_user_mastery AS num
        JOIN nodes AS n ON n.id = num.node_id
        """
    )


def downgrade() -> None:
    op.drop_index("ix_study_activity_space_time", table_name="study_activity_logs")
    op.drop_index("ix_mastery_events_user_node_time", table_name="node_mastery_events")
    op.drop_index("ix_mastery_events_user_time", table_name="node_mastery_events")
    op.drop_index("ix_mastery_events_space_time", table_name="node_mastery_events")
    op.drop_table("node_mastery_events")
    # PostgreSQL cannot safely remove an enum value in-place. Keeping the
    # unused value makes emergency code rollback safe.
