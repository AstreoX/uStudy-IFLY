"""Add teacher assignments, grading, and durable jobs.

Revision ID: assignments_v1
Revises: teacher_presentation_recovery_v1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "assignments_v1"
down_revision: str | None = "teacher_presentation_recovery_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def upgrade() -> None:
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'ASSIGNMENT_GRADED'")
    op.execute("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'ASSIGNMENT_GRADE_UPDATED'")

    op.create_table(
        "assignments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("space_id", UUID, sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("teacher_user_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("instructions", sa.Text(), server_default="", nullable=False),
        sa.Column("difficulty", sa.String(20), server_default="medium", nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("total_questions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("total_score >= 0", name="ck_assignments_total_score"),
    )
    op.create_index("ix_assignments_space_status_due", "assignments", ["space_id", "status", "due_at"])
    op.create_index("ix_assignments_teacher", "assignments", ["teacher_user_id", "created_at"])

    op.create_table(
        "assignment_questions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("assignment_id", UUID, sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_type", sa.String(30), nullable=False),
        sa.Column("question_stem", sa.Text(), nullable=False),
        sa.Column("options", JSONB, nullable=True),
        sa.Column("correct_answer", JSONB, nullable=False),
        sa.Column("rubric", sa.Text(), nullable=True),
        sa.Column("max_score", sa.Float(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("grader_type", sa.String(30), server_default="rule", nullable=False),
        sa.Column("grader_config", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("max_score > 0", name="ck_assignment_questions_score"),
        sa.UniqueConstraint("assignment_id", "order_index", name="uq_assignment_question_order"),
    )
    op.create_index("ix_assignment_questions_assignment", "assignment_questions", ["assignment_id"])

    op.create_table(
        "assignment_recipients",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("assignment_id", UUID, sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("due_at_override", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("assignment_id", "user_id", name="uq_assignment_recipient"),
    )
    op.create_index("ix_assignment_recipients_user", "assignment_recipients", ["user_id", "assignment_id"])

    op.create_table(
        "assignment_submissions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("assignment_id", UUID, sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), server_default="in_progress", nullable=False),
        sa.Column("answers_raw", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("current_question_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("draft_updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grading_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grading_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provisional_score", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("teacher_feedback", sa.Text(), nullable=True),
        sa.Column("grading_error", sa.Text(), nullable=True),
        sa.UniqueConstraint("assignment_id", "user_id", name="uq_assignment_submission_once"),
    )
    op.create_index("ix_assignment_submissions_assignment_status", "assignment_submissions", ["assignment_id", "status"])
    op.create_index("ix_assignment_submissions_user", "assignment_submissions", ["user_id", "assignment_id"])

    op.create_table(
        "assignment_answers",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("submission_id", UUID, sa.ForeignKey("assignment_submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", UUID, sa.ForeignKey("assignment_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_answer", JSONB, nullable=True),
        sa.Column("auto_score", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("review_required", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.UniqueConstraint("submission_id", "question_id", name="uq_assignment_answer_question"),
    )
    op.create_index("ix_assignment_answers_submission", "assignment_answers", ["submission_id"])

    op.create_table(
        "assignment_jobs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("assignment_id", UUID, sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("submission_id", UUID, sa.ForeignKey("assignment_submissions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("requested_by_user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("input_data", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("output_data", JSONB, nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_assignment_jobs_claim", "assignment_jobs", ["status", "available_at", "lease_expires_at"])
    op.create_index("ix_assignment_jobs_assignment", "assignment_jobs", ["assignment_id", "created_at"])
    op.create_index("ix_assignment_jobs_submission", "assignment_jobs", ["submission_id", "created_at"])

    op.create_table(
        "assignment_grade_audits",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("submission_id", UUID, sa.ForeignKey("assignment_submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer_id", UUID, sa.ForeignKey("assignment_answers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewer_user_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("previous_score", sa.Float(), nullable=True),
        sa.Column("new_score", sa.Float(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_assignment_grade_audits_submission", "assignment_grade_audits", ["submission_id", "created_at"])


def downgrade() -> None:
    op.drop_table("assignment_grade_audits")
    op.drop_table("assignment_jobs")
    op.drop_table("assignment_answers")
    op.drop_table("assignment_submissions")
    op.drop_table("assignment_recipients")
    op.drop_table("assignment_questions")
    op.drop_table("assignments")
    # PostgreSQL enum values are intentionally retained on downgrade.
