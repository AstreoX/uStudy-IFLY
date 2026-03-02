"""add feedbacks table

Revision ID: g6h7i8j9k0l1
Revises: f5g6h7i8j9k0
Create Date: 2026-02-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g6h7i8j9k0l1"
down_revision: Union[str, None] = "f5g6h7i8j9k0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create chat_mode enum type
    chat_mode_enum = postgresql.ENUM(
        "quick_chat", "space_chat", name="chatmode", create_type=False
    )
    chat_mode_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "feedbacks",
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
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="The specific AI message that triggered the feedback",
        ),
        sa.Column(
            "chat_mode",
            chat_mode_enum,
            nullable=False,
            comment="quick_chat or space_chat",
        ),
        sa.Column(
            "space_name",
            sa.String(200),
            nullable=True,
            comment="Learning space name if space_chat mode",
        ),
        sa.Column(
            "feedback_content",
            sa.Text(),
            nullable=False,
            comment="User's feedback description",
        ),
        sa.Column(
            "conversation_history",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Complete conversation data including messages, tool calls, and system prompts",
        ),
        sa.Column(
            "user_email",
            sa.String(255),
            nullable=False,
            comment="User's email for reference",
        ),
        sa.Column(
            "user_nickname",
            sa.String(100),
            nullable=False,
            comment="User's display name",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create indexes
    op.create_index("ix_feedbacks_user_id", "feedbacks", ["user_id"])
    op.create_index("ix_feedbacks_conversation_id", "feedbacks", ["conversation_id"])
    op.create_index("ix_feedbacks_created_at", "feedbacks", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_feedbacks_created_at")
    op.drop_index("ix_feedbacks_conversation_id")
    op.drop_index("ix_feedbacks_user_id")
    op.drop_table("feedbacks")

    # Drop enum type
    chat_mode_enum = postgresql.ENUM("quick_chat", "space_chat", name="chatmode")
    chat_mode_enum.drop(op.get_bind(), checkfirst=True)
