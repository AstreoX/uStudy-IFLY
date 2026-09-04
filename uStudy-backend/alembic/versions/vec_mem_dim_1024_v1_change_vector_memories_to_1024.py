"""Change vector memory embeddings to 1024 dimensions

Revision ID: vec_mem_dim_1024_v1
Revises: merge_all_v2
Create Date: 2026-04-28
"""

from typing import Union

from alembic import op

revision: str = "vec_mem_dim_1024_v1"
down_revision: Union[str, None] = "merge_all_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Recreate vector memory embeddings for DashScope text-embedding-v3."""
    op.execute("DROP INDEX IF EXISTS ix_vector_memories_embedding")
    op.execute("DELETE FROM vector_memories")
    op.execute(
        "ALTER TABLE vector_memories "
        "ALTER COLUMN embedding TYPE vector(1024)"
    )
    op.execute(
        """
        CREATE INDEX ix_vector_memories_embedding
        ON vector_memories
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    """Revert vector memory embeddings to the previous 2000 dimensions."""
    op.execute("DROP INDEX IF EXISTS ix_vector_memories_embedding")
    op.execute("DELETE FROM vector_memories")
    op.execute(
        "ALTER TABLE vector_memories "
        "ALTER COLUMN embedding TYPE vector(2000)"
    )
    op.execute(
        """
        CREATE INDEX ix_vector_memories_embedding
        ON vector_memories
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )
