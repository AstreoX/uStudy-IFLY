"""add folders table and folder_id to notes/quizzes

Revision ID: folders_v1
Revises: notifications_v1
Create Date: 2026-03-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "folders_v1"
down_revision: Union[str, None] = "notifications_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create foldercontenttype enum
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'foldercontenttype') THEN
                CREATE TYPE foldercontenttype AS ENUM ('notes', 'quizzes');
            END IF;
        END
        $$;
    """))

    # 2. Create folders table
    op.create_table(
        "folders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "space_id",
            UUID(as_uuid=True),
            sa.ForeignKey("spaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("folders.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "content_type",
            PG_ENUM("notes", "quizzes", name="foldercontenttype", create_type=False),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer, server_default="0", nullable=False),
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
    )
    op.create_index("ix_folders_space_id", "folders", ["space_id"])
    op.create_index("ix_folders_parent_id", "folders", ["parent_id"])

    # 3. Add folder_id to notes
    op.add_column(
        "notes",
        sa.Column(
            "folder_id",
            UUID(as_uuid=True),
            sa.ForeignKey("folders.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_notes_folder_id", "notes", ["folder_id"])

    # 4. Add folder_id to quizzes
    op.add_column(
        "quizzes",
        sa.Column(
            "folder_id",
            UUID(as_uuid=True),
            sa.ForeignKey("folders.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_quizzes_folder_id", "quizzes", ["folder_id"])


def downgrade() -> None:
    op.drop_index("ix_quizzes_folder_id", table_name="quizzes")
    op.drop_column("quizzes", "folder_id")

    op.drop_index("ix_notes_folder_id", table_name="notes")
    op.drop_column("notes", "folder_id")

    op.drop_index("ix_folders_parent_id", table_name="folders")
    op.drop_index("ix_folders_space_id", table_name="folders")
    op.drop_table("folders")

    op.execute(sa.text("DROP TYPE IF EXISTS foldercontenttype"))
