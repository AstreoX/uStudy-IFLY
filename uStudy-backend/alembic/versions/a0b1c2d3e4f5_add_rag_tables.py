"""add RAG tables (document_chunks, document_processing_tasks)

Revision ID: a0b1c2d3e4f5
Revises: 9e5f6g7h8i9j
Create Date: 2026-02-04 22:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "9e5f6g7h8i9j"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create RAG-related tables."""
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Create ProcessingStatus enum
    processing_status_enum = postgresql.ENUM(
        "pending",
        "processing",
        "completed",
        "failed",
        name="processingstatus",
        create_type=False,
    )
    processing_status_enum.create(op.get_bind(), checkfirst=True)

    # 3. Create document_processing_tasks table
    op.create_table(
        "document_processing_tasks",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "processing",
                "completed",
                "failed",
                name="processingstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["space_documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id"),
    )
    op.create_index(
        "ix_doc_processing_document_id",
        "document_processing_tasks",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_doc_processing_status",
        "document_processing_tasks",
        ["status"],
        unique=False,
    )

    # 4. Create document_chunks table with pgvector embedding column
    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("chunk_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["space_documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["spaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add embedding column using raw SQL (pgvector type)
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)")

    # Create indexes
    op.create_index(
        "ix_document_chunks_document_id",
        "document_chunks",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_chunks_space_id",
        "document_chunks",
        ["space_id"],
        unique=False,
    )

    # Create HNSW index for fast vector similarity search
    op.execute(
        """
        CREATE INDEX ix_document_chunks_embedding
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    """Drop RAG-related tables."""
    # Drop indexes
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")
    op.drop_index("ix_document_chunks_space_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")

    # Drop document_chunks table
    op.drop_table("document_chunks")

    # Drop document_processing_tasks table
    op.drop_index("ix_doc_processing_status", table_name="document_processing_tasks")
    op.drop_index(
        "ix_doc_processing_document_id", table_name="document_processing_tasks"
    )
    op.drop_table("document_processing_tasks")

    # Drop enum type
    op.execute("DROP TYPE IF EXISTS processingstatus")

    # Note: We don't drop the vector extension as other tables might use it
