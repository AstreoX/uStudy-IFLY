"""add case-insensitive usernames for experiment accounts

Revision ID: experiment_username_v1
Revises: ai_observability_v1
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "experiment_username_v1"
down_revision: Union[str, None] = "ai_observability_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=64), nullable=True))
    op.execute(
        "CREATE UNIQUE INDEX uq_users_username_lower "
        "ON users (lower(username)) WHERE username IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_users_username_lower")
    op.drop_column("users", "username")
