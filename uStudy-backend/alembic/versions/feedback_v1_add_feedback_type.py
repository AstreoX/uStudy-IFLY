"""add feedback_type column to feedbacks

Revision ID: feedback_v1
Revises: collab_v5
Create Date: 2026-03-14

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "feedback_v1"
down_revision: Union[str, None] = "collab_v5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "feedbacks",
        sa.Column("feedback_type", sa.String(20), nullable=True, server_default="report"),
    )


def downgrade() -> None:
    op.drop_column("feedbacks", "feedback_type")
