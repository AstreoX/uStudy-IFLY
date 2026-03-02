"""add memory_sharing_enabled to spaces

Revision ID: mem_sharing_v1
Revises: vec_mem_table_v1
Create Date: 2026-02-15

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "mem_sharing_v1"
down_revision: Union[str, None] = "vec_mem_table_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add memory_sharing_enabled column to spaces table."""
    op.add_column(
        "spaces",
        sa.Column(
            "memory_sharing_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="是否开启记忆共享（允许其他空间检索本空间记忆）",
        ),
    )


def downgrade() -> None:
    """Remove memory_sharing_enabled column from spaces table."""
    op.drop_column("spaces", "memory_sharing_enabled")
