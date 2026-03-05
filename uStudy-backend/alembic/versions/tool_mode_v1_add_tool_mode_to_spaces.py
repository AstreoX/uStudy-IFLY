"""add tool_mode and enabled_tools to spaces

Revision ID: tool_mode_v1
Revises: quiz_async_v1
Create Date: 2026-03-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "tool_mode_v1"
down_revision: Union[str, None] = "quiz_async_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tool_mode and enabled_tools columns to spaces table."""
    op.add_column(
        "spaces",
        sa.Column(
            "tool_mode",
            sa.String(10),
            nullable=False,
            server_default="auto",
            comment="工具模式：auto（AI按需加载）/ manual（用户自选）",
        ),
    )
    op.add_column(
        "spaces",
        sa.Column(
            "enabled_tools",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="manual 模式下启用的工具名称数组",
        ),
    )


def downgrade() -> None:
    """Remove tool_mode and enabled_tools columns from spaces table."""
    op.drop_column("spaces", "enabled_tools")
    op.drop_column("spaces", "tool_mode")
