"""Add target_tier to activation_codes table.

Revision ID: activation_tier_v1
Revises: citations_v1
Create Date: 2026-03-15
"""

from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "activation_tier_v1"
down_revision: Union[str, None] = "citations_v1"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # 1. Add column as nullable first
    op.add_column(
        "activation_codes",
        sa.Column(
            "target_tier",
            PG_ENUM(
                "FREE", "BASIC", "PREMIUM", "ALPHA", "ULTRA",
                name="subscriptiontier",
                create_type=False,
            ),
            nullable=True,
        ),
    )
    # 2. Backfill existing rows with ALPHA (uppercase per project convention)
    op.execute("UPDATE activation_codes SET target_tier = 'ALPHA' WHERE target_tier IS NULL")
    # 3. Make non-nullable
    op.alter_column("activation_codes", "target_tier", nullable=False)


def downgrade() -> None:
    op.drop_column("activation_codes", "target_tier")
