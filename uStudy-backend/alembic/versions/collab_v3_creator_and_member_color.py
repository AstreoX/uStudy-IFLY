"""collab v3: creator tracking + member color

- Add creator_user_id to notes and space_documents tables
- Add color column to space_members table
- Backfill existing rows: set creator to space owner

Revision ID: collab_v3
Revises: collab_v2
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "collab_v3"
down_revision: Union[str, Sequence[str], None] = "collab_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Notes creator tracking
    op.add_column(
        "notes",
        sa.Column(
            "creator_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 2. SpaceDocuments creator tracking
    op.add_column(
        "space_documents",
        sa.Column(
            "creator_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 3. SpaceMember color
    op.add_column(
        "space_members",
        sa.Column("color", sa.String(7), server_default="#0088FF", nullable=False),
    )

    # 4. Backfill: existing notes → space owner
    op.execute(
        """
        UPDATE notes SET creator_user_id = (
            SELECT user_id FROM spaces WHERE spaces.id = notes.space_id
        ) WHERE creator_user_id IS NULL
        """
    )

    # 5. Backfill: existing documents → space owner
    op.execute(
        """
        UPDATE space_documents SET creator_user_id = (
            SELECT user_id FROM spaces WHERE spaces.id = space_documents.space_id
        ) WHERE creator_user_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("space_members", "color")
    op.drop_column("space_documents", "creator_user_id")
    op.drop_column("notes", "creator_user_id")
