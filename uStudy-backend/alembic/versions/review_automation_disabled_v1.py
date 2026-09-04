"""Default review mode to disabled

Revision ID: review_automation_disabled_v1
Revises: invite_rewards_v1
Create Date: 2026-05-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "review_automation_disabled_v1"
down_revision: Union[str, Sequence[str], None] = "invite_rewards_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE spaces SET review_mode = 0 WHERE review_mode <> 0")
    op.alter_column(
        "spaces",
        "review_mode",
        existing_type=sa.Integer(),
        existing_nullable=False,
        server_default="0",
    )


def downgrade() -> None:
    op.alter_column(
        "spaces",
        "review_mode",
        existing_type=sa.Integer(),
        existing_nullable=False,
        server_default="3",
    )
