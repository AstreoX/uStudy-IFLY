"""add_advanced_edge_type

Revision ID: 6b2c3d4e5f6g
Revises: 5a1b2c3d4e5f
Create Date: 2026-01-31 20:25:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6b2c3d4e5f6g'
down_revision: Union[str, Sequence[str], None] = '5a1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ADVANCED value to edgetype enum."""
    op.execute("ALTER TYPE edgetype ADD VALUE IF NOT EXISTS 'ADVANCED'")


def downgrade() -> None:
    """Cannot remove enum values in PostgreSQL."""
    # PostgreSQL does not support removing enum values directly
    # This would require recreating the type and migrating data
    pass
