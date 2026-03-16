"""fix agenttasktype expand_node to uppercase EXPAND_NODE

Revision ID: expand_node_v2
Revises: expand_node_v1
Create Date: 2026-03-05

v1 误用小写 'expand_node'，SQLAlchemy 实际以枚举成员名称（大写）写库，
需补充 'EXPAND_NODE' 大写值。小写值无法从 PostgreSQL 删除，两者共存无害。

"""
from typing import Sequence, Union

from alembic import op

revision: str = "expand_node_v2"
down_revision: Union[str, None] = "expand_node_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("COMMIT")
    op.execute("ALTER TYPE agenttasktype ADD VALUE IF NOT EXISTS 'EXPAND_NODE'")


def downgrade() -> None:
    pass
