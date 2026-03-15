"""add expand_node to agenttasktype enum

Revision ID: expand_node_v1
Revises: notes_v1
Create Date: 2026-03-05

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "expand_node_v1"
down_revision: Union[str, None] = "notes_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("COMMIT")
    op.execute("ALTER TYPE agenttasktype ADD VALUE IF NOT EXISTS 'expand_node'")


def downgrade() -> None:
    # Cannot remove enum values in PostgreSQL
    # expand_node will remain in agenttasktype enum
    pass
