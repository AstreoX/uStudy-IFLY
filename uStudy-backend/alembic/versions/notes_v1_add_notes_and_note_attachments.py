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
    """Create notes and note_attachments tables (idempotent)."""
    conn = op.get_bind()

    # Create enum type if not exists
    conn.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'noteattachmenttype') THEN
                CREATE TYPE noteattachmenttype AS ENUM ('image', 'file', 'link');
            END IF;
        END$$;
    """))

    # Create notes table if not exists
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS notes (
            id UUID NOT NULL PRIMARY KEY,
            space_id UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
            node_id UUID REFERENCES nodes(id) ON DELETE SET NULL,
            title VARCHAR(200),
            content TEXT,
            sort_order INTEGER DEFAULT 0 NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """))

    # Create indexes if not exist
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_space_id ON notes(space_id);"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_notes_node_id ON notes(node_id);"))

    # Create note_attachments table if not exists
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS note_attachments (
            id UUID NOT NULL PRIMARY KEY,
            note_id UUID NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            attachment_type noteattachmenttype NOT NULL,
            file_url VARCHAR(500),
            original_filename VARCHAR(255),
            file_size INTEGER,
            mime_type VARCHAR(100),
            link_url VARCHAR(2048),
            link_title VARCHAR(500),
            sort_order INTEGER DEFAULT 0 NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        );
    """))

    # Create index if not exists
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_note_attachments_note_id ON note_attachments(note_id);"))


def downgrade() -> None:
    """Drop notes and note_attachments tables."""
    op.drop_table("note_attachments")
    op.drop_table("notes")
    op.execute(sa.text("DROP TYPE IF EXISTS noteattachmenttype;"))
