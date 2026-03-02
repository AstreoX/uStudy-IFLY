"""add debug_info column to quiz_attempts

Revision ID: b1c2d3e4f5g6
Revises: a0b1c2d3e4f5
Create Date: 2026-02-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5g6"
down_revision: Union[str, Sequence[str], None] = "a0b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add debug_info column to quiz_attempts table."""
    op.add_column(
        "quiz_attempts",
        sa.Column("debug_info", JSON(), nullable=True),
    )


def downgrade() -> None:
    """Remove debug_info column from quiz_attempts table."""
    op.drop_column("quiz_attempts", "debug_info")
