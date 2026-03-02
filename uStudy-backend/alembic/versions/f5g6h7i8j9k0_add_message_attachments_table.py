"""add message_attachments table

Revision ID: f5g6h7i8j9k0
Revises: e4f5g6h7i8j9
Create Date: 2026-02-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5g6h7i8j9k0"
down_revision: Union[str, None] = "e4f5g6h7i8j9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create AttachmentType enum
    attachment_type_enum = postgresql.ENUM(
        "image", "file", name="attachmenttype", create_type=False
    )
    attachment_type_enum.create(op.get_bind(), checkfirst=True)

    # Create message_attachments table
    op.create_table(
        "message_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "attachment_type",
            postgresql.ENUM("image", "file", name="attachmenttype", create_type=False),
            nullable=False,
        ),
        sa.Column("file_url", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Create indexes
    op.create_index(
        "ix_message_attachments_message_id",
        "message_attachments",
        ["message_id"],
    )
    op.create_index(
        "ix_message_attachments_user_id",
        "message_attachments",
        ["user_id"],
    )
    op.create_index(
        "ix_message_attachments_created_at",
        "message_attachments",
        ["created_at"],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_message_attachments_created_at")
    op.drop_index("ix_message_attachments_user_id")
    op.drop_index("ix_message_attachments_message_id")

    # Drop table
    op.drop_table("message_attachments")

    # Drop enum
    attachment_type_enum = postgresql.ENUM(
        "image", "file", name="attachmenttype", create_type=False
    )
    attachment_type_enum.drop(op.get_bind(), checkfirst=True)
