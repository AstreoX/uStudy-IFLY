"""add user_mcp_services table for custom MCP server configuration

Revision ID: mcp_services_v1
Revises: agent_todo_v1
Create Date: 2026-04-02

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers, used by Alembic.
revision: str = "mcp_services_v1"
down_revision: Union[str, None] = "agent_todo_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user_mcp_services table."""
    op.create_table(
        "user_mcp_services",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("tools_cache", JSON(), nullable=True),
        sa.Column(
            "last_connected_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("user_id", "url", name="uq_user_mcp_service_url"),
    )
    op.create_index(
        "ix_user_mcp_services_user_id", "user_mcp_services", ["user_id"]
    )


def downgrade() -> None:
    """Drop user_mcp_services table."""
    op.drop_index("ix_user_mcp_services_user_id", table_name="user_mcp_services")
    op.drop_table("user_mcp_services")
