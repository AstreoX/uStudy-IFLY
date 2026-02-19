"""add app_usage_daily table

Revision ID: app_usage_v1
Revises: review_sched_v1
Create Date: 2026-02-19 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "app_usage_v1"
down_revision: Union[str, None] = "review_sched_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_usage_daily",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("total_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "usage_date", name="uq_app_usage_daily_user_date"),
    )
    op.create_index(
        "ix_app_usage_daily_user_date",
        "app_usage_daily",
        ["user_id", "usage_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_app_usage_daily_user_date", table_name="app_usage_daily")
    op.drop_table("app_usage_daily")
