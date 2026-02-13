"""add alpha tier and activation_codes table

Revision ID: m2n3o4p5q6r7
Revises: l1m2n3o4p5q6
Create Date: 2026-02-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "m2n3o4p5q6r7"
down_revision: Union[str, None] = "l1m2n3o4p5q6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add ALPHA to subscriptiontier enum
    op.execute("COMMIT")
    op.execute("ALTER TYPE subscriptiontier ADD VALUE IF NOT EXISTS 'alpha'")

    # 2. Create activation_codes table
    op.execute("BEGIN")
    op.create_table(
        "activation_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("used_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validity_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["used_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
    )

    # 3. Create indexes
    op.create_index(
        "ix_activation_codes_code", "activation_codes", ["code"], unique=True
    )
    op.create_index(
        "ix_activation_codes_used_by", "activation_codes", ["used_by"], unique=False
    )


def downgrade() -> None:
    # Drop indexes and table
    op.drop_index("ix_activation_codes_used_by", table_name="activation_codes")
    op.drop_index("ix_activation_codes_code", table_name="activation_codes")
    op.drop_table("activation_codes")

    # Note: Cannot remove enum values in PostgreSQL
    # ALPHA will remain in subscriptiontier enum
