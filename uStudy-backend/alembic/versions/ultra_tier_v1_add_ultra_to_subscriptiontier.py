"""add ULTRA to subscriptiontier enum

Revision ID: ultra_tier_v1
Revises: tool_mode_v1
Create Date: 2026-03-04

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ultra_tier_v1"
down_revision: Union[str, None] = "tool_mode_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("COMMIT")
    op.execute("ALTER TYPE subscriptiontier ADD VALUE IF NOT EXISTS 'ULTRA'")


def downgrade() -> None:
    # Cannot remove enum values in PostgreSQL
    # ULTRA will remain in subscriptiontier enum
    pass
