"""add in-progress draft fields to quiz_attempts

Revision ID: quiz_draft_v1
Revises: merge_all_heads_v2
Create Date: 2026-03-25 18:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "quiz_draft_v1"
down_revision: Union[str, Sequence[str], None] = "merge_all_heads_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "quiz_attempts",
        sa.Column(
            "current_question_index",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Current question index for resumable quiz drafts",
        ),
    )
    op.add_column(
        "quiz_attempts",
        sa.Column(
            "draft_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="Last updated timestamp for quiz drafts",
        ),
    )


def downgrade() -> None:
    op.drop_column("quiz_attempts", "draft_updated_at")
    op.drop_column("quiz_attempts", "current_question_index")
