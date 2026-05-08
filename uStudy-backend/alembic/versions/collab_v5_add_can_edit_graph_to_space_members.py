"""add can_edit_graph column to space_members

Revision ID: collab_v5
Revises: collab_v4
Create Date: 2026-03-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "collab_v5"
down_revision: Union[str, None] = "collab_v4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "space_members",
        sa.Column(
            "can_edit_graph",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="是否允许修改知识图谱结构",
        ),
    )


def downgrade() -> None:
    op.drop_column("space_members", "can_edit_graph")
