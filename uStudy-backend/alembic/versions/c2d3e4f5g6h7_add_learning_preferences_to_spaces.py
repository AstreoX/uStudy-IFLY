"""add learning_preferences to spaces

Revision ID: c2d3e4f5g6h7
Revises: b1c2d3e4f5g6
Create Date: 2025-02-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5g6h7"
down_revision: Union[str, None] = "b1c2d3e4f5g6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "spaces",
        sa.Column(
            "learning_preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="学习偏好设置",
        ),
    )


def downgrade() -> None:
    op.drop_column("spaces", "learning_preferences")
