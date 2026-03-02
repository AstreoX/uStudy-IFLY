"""add api_usage_logs table

Revision ID: i8j9k0l1m2n3
Revises: h7i8j9k0l1m2
Create Date: 2026-02-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "i8j9k0l1m2n3"
down_revision: Union[str, None] = "h7i8j9k0l1m2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create usage_type enum
    usage_type_enum = postgresql.ENUM(
        "chat_llm",
        "quick_chat_llm",
        "embedding",
        "agent_llm",
        name="usagetype",
        create_type=False,
    )
    usage_type_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "api_usage_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "space_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("spaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("usage_type", usage_type_enum, nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "completion_tokens", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "estimated_cost_cents", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "request_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create indexes for common query patterns
    # Composite index (user_id, created_at) covers user_id-only queries
    op.create_index(
        "ix_api_usage_logs_user_created", "api_usage_logs", ["user_id", "created_at"]
    )
    op.create_index("ix_api_usage_logs_usage_type", "api_usage_logs", ["usage_type"])
    op.create_index("ix_api_usage_logs_created_at", "api_usage_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_api_usage_logs_created_at")
    op.drop_index("ix_api_usage_logs_usage_type")
    op.drop_index("ix_api_usage_logs_user_created")
    op.drop_table("api_usage_logs")

    usage_type_enum = postgresql.ENUM(
        "chat_llm",
        "quick_chat_llm",
        "embedding",
        "agent_llm",
        name="usagetype",
    )
    usage_type_enum.drop(op.get_bind(), checkfirst=True)
