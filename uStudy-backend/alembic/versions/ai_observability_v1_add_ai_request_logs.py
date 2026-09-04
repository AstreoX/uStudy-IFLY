"""add ai request observability logs

Revision ID: ai_observability_v1
Revises: payment_notify_logs_v1
Create Date: 2026-06-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "ai_observability_v1"
down_revision: Union[str, Sequence[str], None] = "payment_notify_logs_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_request_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("request_kind", sa.String(length=32), nullable=False),
        sa.Column("source_module", sa.String(length=80), nullable=True),
        sa.Column("source_operation", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("http_status_code", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("ttft_ms", sa.Integer(), nullable=True),
        sa.Column("last_chunk_gap_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("retry_reason", sa.String(length=120), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=True),
        sa.Column("context_chars", sa.Integer(), nullable=True),
        sa.Column("tool_result_chars", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_request_logs_created_at", "ai_request_logs", ["created_at"])
    op.create_index(
        "ix_ai_request_logs_status_created", "ai_request_logs", ["status", "created_at"]
    )
    op.create_index(
        "ix_ai_request_logs_model_created", "ai_request_logs", ["model", "created_at"]
    )
    op.create_index(
        "ix_ai_request_logs_source_created",
        "ai_request_logs",
        ["source_module", "source_operation", "created_at"],
    )
    op.create_index(
        "ix_ai_request_logs_user_created", "ai_request_logs", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_request_logs_user_created", table_name="ai_request_logs")
    op.drop_index("ix_ai_request_logs_source_created", table_name="ai_request_logs")
    op.drop_index("ix_ai_request_logs_model_created", table_name="ai_request_logs")
    op.drop_index("ix_ai_request_logs_status_created", table_name="ai_request_logs")
    op.drop_index("ix_ai_request_logs_created_at", table_name="ai_request_logs")
    op.drop_table("ai_request_logs")
