"""change embedding dimension to 2000 for qwen3-embedding-8b

Revision ID: emb_dim_2000_v1
Revises: o4p5q6r7s8t9
Create Date: 2026-02-15

Note: HNSW index max dimension is 2000, so we use 2000 instead of 4096.
qwen3-embedding-8b supports flexible dimensions (32-4096).

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "emb_dim_2000_v1"
down_revision: Union[str, None] = "o4p5q6r7s8t9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change embedding column dimension from 1536 to 2000."""
    # 1. Drop the existing HNSW index
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding")

    # 2. Clear existing embeddings (they are incompatible with the new dimension)
    op.execute("UPDATE document_chunks SET embedding = NULL")

    # 3. Change the embedding column dimension (2000 is HNSW max)
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(2000)")

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
        SET status = 'PENDING', error_message = NULL, started_at = NULL, completed_at = NULL
        WHERE status = 'COMPLETED'
        """
    )


def downgrade() -> None:
    """Revert embedding column dimension from 2000 to 1536."""
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
