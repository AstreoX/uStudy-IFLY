"""add status and user_answers_raw to quiz_attempts

Revision ID: quiz_async_v1
Revises: tool_calls_v1
Create Date: 2026-03-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "quiz_async_v1"
down_revision: Union[str, Sequence[str], None] = "tool_calls_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "quiz_attempts",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="completed",
            comment="Async evaluation status: pending/evaluating/completed/failed",
        ),
    )
    op.add_column(
        "quiz_attempts",
        sa.Column(
            "user_answers_raw",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
            comment="Raw user answers for async background evaluation",
        ),
    )


def downgrade() -> None:
    op.drop_column("quiz_attempts", "user_answers_raw")
    op.drop_column("quiz_attempts", "status")
