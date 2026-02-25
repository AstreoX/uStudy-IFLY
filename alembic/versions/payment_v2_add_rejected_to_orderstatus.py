"""add rejected status to orderstatus enum

Revision ID: payment_v2
Revises: payment_v1
Create Date: 2026-02-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "payment_v2"
down_revision: Union[str, None] = "payment_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'rejected'")


def downgrade() -> None:
    # PostgreSQL does not support removing individual enum values.
    # A full enum recreation would be needed, which is rarely worth the risk.
    pass
