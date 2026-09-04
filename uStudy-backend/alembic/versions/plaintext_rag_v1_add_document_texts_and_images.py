"""Add document_texts and document_images tables; drop document_chunks.embedding

Revision ID: plaintext_rag_v1
Revises: tool_mode_v1
Create Date: 2026-04-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "plaintext_rag_v1"
down_revision: Union[str, None] = "tool_mode_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create document_texts table
    op.create_table(
        "document_texts",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["document_id"], ["space_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_document_texts_document_id"),
    )

    # Add tsvector column via raw SQL (not a standard SA type)
    op.execute(
        "ALTER TABLE document_texts ADD COLUMN content_tsv tsvector"
    )

    op.create_index("ix_document_texts_space_id", "document_texts", ["space_id"])

    # GIN index for full-text BM25 search
    op.execute(
        "CREATE INDEX ix_document_texts_content_tsv ON document_texts USING GIN(content_tsv)"
    )

    # 2. Create document_images table
    op.create_table(
        "document_images",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_text_id", UUID(as_uuid=True), nullable=True),
        sa.Column("page_num", sa.Integer(), nullable=True),
        sa.Column("image_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("vlm_description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["document_id"], ["space_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_text_id"], ["document_texts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_document_images_space_id", "document_images", ["space_id"])
    op.create_index(
        "ix_document_images_document_text_id", "document_images", ["document_text_id"]
    )

    # 3. Drop embedding column from document_chunks
    op.execute("DROP INDEX IF EXISTS document_chunks_embedding_idx")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")


def downgrade() -> None:
    # Re-add embedding column
    op.execute(
        "ALTER TABLE document_chunks ADD COLUMN embedding vector(2000)"
    )

    # Drop document_images
    op.drop_index("ix_document_images_document_text_id", table_name="document_images")
    op.drop_index("ix_document_images_space_id", table_name="document_images")
    op.drop_table("document_images")

    # Drop document_texts
    op.execute("DROP INDEX IF EXISTS ix_document_texts_content_tsv")
    op.drop_index("ix_document_texts_space_id", table_name="document_texts")
    op.drop_table("document_texts")
