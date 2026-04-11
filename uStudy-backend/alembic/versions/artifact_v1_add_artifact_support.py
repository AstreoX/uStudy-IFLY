"""Add artifact support: note_type, metadata on notes; artifact_note_id on conversations; GENERATE_ARTIFACT enum

Revision ID: artifact_v1
Revises: token_family_v1
Create Date: 2026-03-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "artifact_v1"
down_revision: Union[str, None] = "token_family_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add note_type and metadata to notes
    op.add_column(
        "notes",
        sa.Column("note_type", sa.String(50), server_default="text", nullable=False),
    )
    op.add_column(
        "notes",
        sa.Column("metadata", JSONB(), nullable=True),
    )

    # 2. Add artifact_note_id FK to conversations
    op.add_column(
        "conversations",
        sa.Column("artifact_note_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_artifact_note_id",
        "conversations",
        "notes",
        ["artifact_note_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_conversations_artifact_note_id",
        "conversations",
        ["artifact_note_id"],
    )

    # 3. Add GENERATE_ARTIFACT to agenttasktype enum (uppercase name!)
    op.execute("ALTER TYPE agenttasktype ADD VALUE IF NOT EXISTS 'GENERATE_ARTIFACT'")


def downgrade() -> None:
    # Clear artifact FK references first
    op.execute("UPDATE conversations SET artifact_note_id = NULL WHERE artifact_note_id IS NOT NULL")
    op.drop_index("ix_conversations_artifact_note_id", table_name="conversations")
    op.drop_constraint("fk_conversations_artifact_note_id", "conversations", type_="foreignkey")
    op.drop_column("conversations", "artifact_note_id")
    # Normalize note_type before dropping column
    op.execute("UPDATE notes SET note_type = 'text' WHERE note_type != 'text'")
    op.drop_column("notes", "metadata")
    op.drop_column("notes", "note_type")
    # Note: Cannot remove enum value from PostgreSQL enum type
