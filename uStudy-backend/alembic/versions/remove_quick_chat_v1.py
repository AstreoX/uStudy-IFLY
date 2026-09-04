"""remove quick chat runtime data and require space-bound conversations

Revision ID: remove_quick_chat_v1
Revises: experiment_username_v1
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "remove_quick_chat_v1"
down_revision: Union[str, None] = "experiment_username_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # These rows belong exclusively to the removed no-space chat mode.
    op.execute("DELETE FROM feedbacks WHERE chat_mode::text = 'quick_chat'")
    op.execute("DELETE FROM api_usage_logs WHERE usage_type::text = 'quick_chat_llm'")
    op.execute("DELETE FROM conversations WHERE space_id IS NULL")

    op.execute("DROP TABLE IF EXISTS quick_chat_tool_tasks CASCADE")
    op.execute("DROP TYPE IF EXISTS quickchattooltaskstage")
    op.execute("DROP TYPE IF EXISTS quickchattooltaskstatus")

    op.alter_column(
        "conversations",
        "space_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )


def downgrade() -> None:
    # Deleted conversations and messages cannot be restored. Downgrade only
    # recreates the legacy empty schema for emergency code rollback.
    op.alter_column(
        "conversations",
        "space_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    status_enum = postgresql.ENUM(
        "running", "done", "failed", name="quickchattooltaskstatus"
    )
    stage_enum = postgresql.ENUM(
        "queued",
        "space_created",
        "kg_running",
        "kg_done",
        "binding",
        "binding_done",
        "binding_failed",
        "kg_failed",
        "timeout",
        "cleanup_done",
        "cleanup_failed",
        name="quickchattooltaskstage",
    )
    status_enum.create(op.get_bind(), checkfirst=True)
    stage_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "quick_chat_tool_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_call_id", sa.String(length=100), nullable=False),
        sa.Column("tool_name", sa.String(length=50), nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("stage", stage_enum, nullable=False),
        sa.Column(
            "space_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("spaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "kg_task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("request_payload", postgresql.JSONB(), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(), nullable=True),
        sa.Column("error_stage", sa.String(length=50), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tool_call_id", name="uq_quick_chat_tool_tasks_tool_call_id"),
    )
    op.create_index(
        "ix_quick_chat_tool_tasks_conversation_status",
        "quick_chat_tool_tasks",
        ["conversation_id", "status"],
    )
    op.create_index(
        "ix_quick_chat_tool_tasks_user_status",
        "quick_chat_tool_tasks",
        ["user_id", "status"],
    )
