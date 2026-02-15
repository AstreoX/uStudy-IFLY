"""add vector_memories table for semantic memory storage

Revision ID: vec_mem_table_v1
Revises: emb_dim_2000_v1
Create Date: 2026-02-15

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "vec_mem_table_v1"
down_revision: Union[str, None] = "emb_dim_2000_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create vector_memories table with pgvector embedding column."""
    # 1. Create MemoryType enum
    memory_type_enum = postgresql.ENUM(
        "long_term",
        "space",
        name="memorytype",
        create_type=False,
    )
    memory_type_enum.create(op.get_bind(), checkfirst=True)

    # 2. Create vector_memories table
    op.create_table(
        "vector_memories",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "memory_type",
            postgresql.ENUM(
                "long_term",
                "space",
                name="memorytype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("extra_data", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["spaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. Add embedding column using raw SQL (pgvector type, 2000 dimensions)
    op.execute("ALTER TABLE vector_memories ADD COLUMN embedding vector(2000) NOT NULL")

    # 4. Create standard indexes
    op.create_index(
        "ix_vector_memories_user_id",
        "vector_memories",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_vector_memories_space_id",
        "vector_memories",
        ["space_id"],
        unique=False,
    )
    op.create_index(
        "ix_vector_memories_user_type",
        "vector_memories",
        ["user_id", "memory_type"],
        unique=False,
    )

    # 5. Create HNSW index for fast vector similarity search
    op.execute(
        """
        CREATE INDEX ix_vector_memories_embedding
        ON vector_memories
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    """Drop vector_memories table."""
    # Drop HNSW index
    op.execute("DROP INDEX IF EXISTS ix_vector_memories_embedding")

    # Drop standard indexes
    op.drop_index("ix_vector_memories_user_type", table_name="vector_memories")
    op.drop_index("ix_vector_memories_space_id", table_name="vector_memories")
    op.drop_index("ix_vector_memories_user_id", table_name="vector_memories")

    # Drop table
    op.drop_table("vector_memories")

    # Drop enum type
    op.execute("DROP TYPE IF EXISTS memorytype")
