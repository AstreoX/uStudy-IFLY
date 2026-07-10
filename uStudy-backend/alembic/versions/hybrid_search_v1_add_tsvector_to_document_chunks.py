"""add tsvector column and GIN index to document_chunks for hybrid search

Revision ID: hybrid_search_v1
Revises: collab_v5
Create Date: 2026-03-14

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

# revision identifiers, used by Alembic.
revision: str = "hybrid_search_v1"
down_revision: Union[str, None] = "feedback_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 添加 tsvector 列
    op.add_column(
        "document_chunks",
        sa.Column("content_tsv", TSVECTOR, nullable=True),
    )

    # 2. 创建 GIN 索引
    op.create_index(
        "ix_document_chunks_content_tsv",
        "document_chunks",
        ["content_tsv"],
        postgresql_using="gin",
    )

    # 3. 初步填充（simple 分词器按空格/标点切分，后续用 jieba 回填脚本精确处理）
    op.execute(
        "UPDATE document_chunks SET content_tsv = to_tsvector('simple', content) WHERE content_tsv IS NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_content_tsv", table_name="document_chunks")
    op.drop_column("document_chunks", "content_tsv")
