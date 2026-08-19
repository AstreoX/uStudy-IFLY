"""smart review system: SM-2 algorithm, review mode, email log

Revision ID: review_sm2_v1
Revises: vec_mem_table_v1
Create Date: 2026-03-17

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "review_sm2_v1"
down_revision: Union[str, None] = "vec_mem_table_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add SM-2 columns to review_schedules
    op.add_column(
        "review_schedules",
        sa.Column("ease_factor", sa.Float(), nullable=False, server_default="2.5"),
    )
    op.add_column(
        "review_schedules",
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "review_schedules",
        sa.Column("quality_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "review_schedules",
        sa.Column("review_quiz_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_review_schedules_review_quiz_id",
        "review_schedules",
        "quizzes",
        ["review_quiz_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 2. Add review_mode to spaces
    op.add_column(
        "spaces",
        sa.Column("review_mode", sa.Integer(), nullable=False, server_default="3"),
    )

    # 3. Add is_review_quiz to quizzes
    op.add_column(
        "quizzes",
        sa.Column(
            "is_review_quiz", sa.Boolean(), nullable=False, server_default="false"
        ),
    )

    # 4. Add GENERATE_REVIEW_QUIZ to agenttasktype enum
    op.execute("COMMIT")
    op.execute(
        "ALTER TYPE agenttasktype ADD VALUE IF NOT EXISTS 'GENERATE_REVIEW_QUIZ'"
    )

    # 5. Create review_email_log table
    op.create_table(
        "review_email_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email_type", sa.String(30), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("spaces_included", JSONB, nullable=True),
        sa.Column("quiz_ids", JSONB, nullable=True),
    )
    op.create_index(
        "idx_review_email_user_type_date",
        "review_email_log",
        ["user_id", "email_type", "sent_at"],
    )


def downgrade() -> None:
    # Drop review_email_log table
    op.drop_index("idx_review_email_user_type_date", table_name="review_email_log")
    op.drop_table("review_email_log")

    # Drop new columns
    op.drop_column("quizzes", "is_review_quiz")
    op.drop_column("spaces", "review_mode")
    op.drop_constraint("fk_review_schedules_review_quiz_id", "review_schedules", type_="foreignkey")
    op.drop_column("review_schedules", "review_quiz_id")
    op.drop_column("review_schedules", "quality_score")
    op.drop_column("review_schedules", "interval_days")
    op.drop_column("review_schedules", "ease_factor")

    # Cannot remove enum values in PostgreSQL
