"""add quick_chat_tool_tasks table

Revision ID: p1q2r3s4t5u6
Revises: review_sched_v2
Create Date: 2026-02-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "p1q2r3s4t5u6"
down_revision: Union[str, None] = "review_sched_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


quick_chat_tool_task_status_enum = ENUM(
    "running",
    "done",
    "failed",
    name="quickchattooltaskstatus",
    create_type=False,
)

quick_chat_tool_task_stage_enum = ENUM(
    "queued",
    "space_created",
    "kg_running",
    "kg_done",
    "binding",
    "binding_done",
    "kg_failed",
    "binding_failed",
    "timeout",
    "cleanup_done",
    "cleanup_failed",
    name="quickchattooltaskstage",
    create_type=False,
)


def upgrade() -> None:
    quick_chat_tool_task_status_enum.create(op.get_bind(), checkfirst=True)
    quick_chat_tool_task_stage_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "quick_chat_tool_tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_call_id", sa.String(length=100), nullable=False),
        sa.Column("tool_name", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            quick_chat_tool_task_status_enum,
            nullable=False,
            server_default="running",
        ),
        sa.Column(
            "stage",
            quick_chat_tool_task_stage_enum,
            nullable=False,
            server_default="queued",
        ),
        sa.Column(
            "space_id",
            UUID(as_uuid=True),
            sa.ForeignKey("spaces.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "kg_task_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_message_id",
            UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("request_payload", JSONB, nullable=False),
        sa.Column("result_payload", JSONB, nullable=True),
        sa.Column("error_stage", sa.String(length=50), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tool_call_id", name="uq_quick_chat_tool_tasks_tool_call_id"),
    )

    op.create_index(
        "ix_quick_chat_tool_tasks_conversation_status",
        "quick_chat_tool_tasks",
        ["conversation_id", "status"],
    )
    op.create_index(
        "ix_quick_chat_tool_tasks_tool_call_id",
        "quick_chat_tool_tasks",
        ["tool_call_id"],
        unique=True,
    )
    op.create_index(
        "ix_quick_chat_tool_tasks_user_status",
        "quick_chat_tool_tasks",
        ["user_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_quick_chat_tool_tasks_user_status", table_name="quick_chat_tool_tasks"
    )
    op.drop_index(
        "ix_quick_chat_tool_tasks_tool_call_id", table_name="quick_chat_tool_tasks"
    )
    op.drop_index(
        "ix_quick_chat_tool_tasks_conversation_status",
        table_name="quick_chat_tool_tasks",
    )
    op.drop_table("quick_chat_tool_tasks")

    quick_chat_tool_task_stage_enum.drop(op.get_bind(), checkfirst=True)
    quick_chat_tool_task_status_enum.drop(op.get_bind(), checkfirst=True)
