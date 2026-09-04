"""Add isolated OJ programming question support.

Revision ID: assignments_oj_v1
Revises: assignments_v1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "assignments_oj_v1"
down_revision: str | None = "assignments_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def upgrade() -> None:
    op.add_column("assignment_questions", sa.Column("public_config", JSONB, nullable=True))

    op.create_table(
        "assignment_oj_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("assignment_id", UUID, sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", UUID, sa.ForeignKey("assignment_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submission_id", UUID, sa.ForeignKey("assignment_submissions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_type", sa.String(20), nullable=False),
        sa.Column("manager_run_id", sa.String(100), nullable=True),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=True),
        sa.Column("source_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("problem_version_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(40), server_default="pending", nullable=False),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_assignment_oj_runs_user_created", "assignment_oj_runs", ["user_id", "created_at"])
    op.create_index("ix_assignment_oj_runs_status", "assignment_oj_runs", ["status", "created_at"])
    op.create_index("ix_assignment_oj_runs_submission", "assignment_oj_runs", ["submission_id", "question_id"])

    op.add_column("assignment_answers", sa.Column("grader_result", JSONB, nullable=True))
    op.add_column(
        "assignment_answers",
        sa.Column("oj_run_id", UUID, sa.ForeignKey("assignment_oj_runs.id", ondelete="SET NULL"), nullable=True),
    )
    op.alter_column(
        "assignment_answers", "status", existing_type=sa.String(20), type_=sa.String(40), existing_nullable=False
    )


def downgrade() -> None:
    # Legacy assignment answers only understand the short generic statuses.
    # Normalize OJ verdicts before shrinking VARCHAR(40) back to VARCHAR(20),
    # otherwise rows such as `memory_limit_exceeded` make downgrade fail.
    op.execute(
        """
        UPDATE assignment_answers
        SET status = CASE
            WHEN status = 'accepted' THEN 'correct'
            WHEN status IN (
                'wrong_answer', 'compile_error', 'runtime_error',
                'time_limit_exceeded', 'memory_limit_exceeded',
                'output_limit_exceeded', 'dangerous_syscall'
            ) THEN 'wrong'
            WHEN status = 'system_error' THEN 'failed'
            ELSE LEFT(status, 20)
        END
        WHERE length(status) > 20 OR status IN (
            'accepted', 'wrong_answer', 'compile_error', 'runtime_error',
            'time_limit_exceeded', 'memory_limit_exceeded',
            'output_limit_exceeded', 'dangerous_syscall', 'system_error'
        )
        """
    )
    op.alter_column(
        "assignment_answers", "status", existing_type=sa.String(40), type_=sa.String(20), existing_nullable=False
    )
    op.drop_column("assignment_answers", "oj_run_id")
    op.drop_column("assignment_answers", "grader_result")
    op.drop_table("assignment_oj_runs")
    op.drop_column("assignment_questions", "public_config")
