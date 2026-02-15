"""change embedding dimension to 4096 for qwen3-embedding-8b

Revision ID: p5q6r7s8t9u0
Revises: o4p5q6r7s8t9
Create Date: 2026-02-15

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p5q6r7s8t9u0"
down_revision: Union[str, None] = "o4p5q6r7s8t9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change embedding column dimension from 1536 to 4096."""
    # 1. Drop the existing HNSW index
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")

    # 2. Clear existing embeddings (they are incompatible with the new dimension)
    op.execute("UPDATE document_chunks SET embedding = NULL")

    # 3. Change the embedding column dimension
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(4096)")

    # 4. Recreate the HNSW index with the new dimension
    op.execute(
        """
        CREATE INDEX ix_document_chunks_embedding
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # 5. Reset processing tasks so documents will be re-processed
    op.execute(
        """
        UPDATE document_processing_tasks
        SET status = 'pending', error_message = NULL, started_at = NULL, completed_at = NULL
        WHERE status = 'completed'
        """
    )


def downgrade() -> None:
    """Revert embedding column dimension from 4096 to 1536."""
    # 1. Drop the HNSW index
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")

    # 2. Clear existing embeddings
    op.execute("UPDATE document_chunks SET embedding = NULL")

    # 3. Change the embedding column dimension back
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1536)")

    # 4. Recreate the HNSW index
    op.execute(
        """
        CREATE INDEX ix_document_chunks_embedding
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )
