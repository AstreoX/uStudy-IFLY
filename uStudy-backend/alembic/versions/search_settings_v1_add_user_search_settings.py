"""add user_search_settings table

Revision ID: search_settings_v1
Revises: payment_qr_v1
Create Date: 2026-03-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "search_settings_v1"
down_revision: Union[str, Sequence[str], None] = "payment_qr_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_search_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("web_search_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("academic_search_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("encyclopedia_search_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("course_search_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_search_settings_user", "user_search_settings", ["user_id"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_search_settings_user", table_name="user_search_settings")
    op.drop_table("user_search_settings")
