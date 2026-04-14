"""add space_share_codes table for space sharing

Revision ID: share_v1
Revises: calendar_v1
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "share_v1"
down_revision: Union[str, Sequence[str], None] = "calendar_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create space_share_codes table (idempotent)."""
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS space_share_codes (
            id UUID NOT NULL PRIMARY KEY,
            code VARCHAR(8) NOT NULL UNIQUE,
            space_id UUID NOT NULL UNIQUE REFERENCES spaces(id) ON DELETE CASCADE,
            creator_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """))

    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_space_share_codes_code ON space_share_codes(code);"
    ))


def downgrade() -> None:
    """Drop space_share_codes table."""
    op.drop_table("space_share_codes")
