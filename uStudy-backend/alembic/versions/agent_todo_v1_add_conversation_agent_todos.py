"""add conversation_agent_todos table

Revision ID: agent_todo_v1
Revises: quiz_draft_v1
Create Date: 2026-04-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "agent_todo_v1"
down_revision: Union[str, Sequence[str], None] = "quiz_draft_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "conversation_agent_todos",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("task_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('pending', 'completed')",
            name="ck_conversation_agent_todos_status",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "task_id",
            name="uq_conversation_agent_todos_conversation_task_id",
        ),
        sa.UniqueConstraint(
            "conversation_id",
            "sort_order",
            name="uq_conversation_agent_todos_conversation_sort_order",
        ),
    )
    op.create_index(
        "ix_conversation_agent_todos_conversation_sort",
        "conversation_agent_todos",
        ["conversation_id", "sort_order"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_conversation_agent_todos_conversation_sort",
        table_name="conversation_agent_todos",
    )
    op.drop_table("conversation_agent_todos")
