"""add notes and note_attachments tables

Revision ID: notes_v1
Revises: ultra_tier_v1
Create Date: 2026-03-04 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "notes_v1"
down_revision: Union[str, Sequence[str], None] = "ultra_tier_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create notes and note_attachments tables."""
    # Create enum type (create_type=False prevents SQLAlchemy from auto-creating during table creation)
    note_attachment_type = sa.Enum("image", "file", "link", name="noteattachmenttype", create_type=False)
    note_attachment_type.create(op.get_bind(), checkfirst=True)

    # Create notes table
    op.create_table(
        "notes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("space_id", sa.UUID(), nullable=False),
        sa.Column("node_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["node_id"], ["nodes.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_notes_space_id", "notes", ["space_id"])
    op.create_index("ix_notes_node_id", "notes", ["node_id"])

    # Create note_attachments table
    op.create_table(
        "note_attachments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("note_id", sa.UUID(), nullable=False),
        sa.Column("attachment_type", note_attachment_type, nullable=False),
        sa.Column("file_url", sa.String(500), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("link_url", sa.String(2048), nullable=True),
        sa.Column("link_title", sa.String(500), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["note_id"], ["notes.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_note_attachments_note_id", "note_attachments", ["note_id"])


def downgrade() -> None:
    """Drop notes and note_attachments tables."""
    op.drop_table("note_attachments")
    op.drop_table("notes")
    sa.Enum(name="noteattachmenttype").drop(op.get_bind(), checkfirst=True)
