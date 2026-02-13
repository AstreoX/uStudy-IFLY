"""add pending_client_tool_requests table

Revision ID: n3o4p5q6r7s8
Revises: m2n3o4p5q6r7
Create Date: 2026-02-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "n3o4p5q6r7s8"
down_revision: Union[str, None] = "m2n3o4p5q6r7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pending_client_tool_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_call_id", sa.String(100), nullable=False),
        sa.Column("tool_name", sa.String(50), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="pending"
        ),
        sa.Column("result_data", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tool_call_id", name="uq_pending_tool_call_id"),
    )

    op.create_index(
        "ix_pending_client_tool_requests_conv_id",
        "pending_client_tool_requests",
        ["conversation_id"],
    )
    op.create_index(
        "ix_pending_client_tool_requests_tool_call_id",
        "pending_client_tool_requests",
        ["tool_call_id"],
        unique=True,
    )
    op.create_index(
        "ix_pending_client_tool_requests_status",
        "pending_client_tool_requests",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_pending_client_tool_requests_status",
        table_name="pending_client_tool_requests",
    )
    op.drop_index(
        "ix_pending_client_tool_requests_tool_call_id",
        table_name="pending_client_tool_requests",
    )
    op.drop_index(
        "ix_pending_client_tool_requests_conv_id",
        table_name="pending_client_tool_requests",
    )
    op.drop_table("pending_client_tool_requests")
