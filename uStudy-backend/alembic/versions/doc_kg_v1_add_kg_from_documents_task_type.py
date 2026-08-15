"""add generate_knowledge_graph_from_documents to agenttasktype enum

Revision ID: doc_kg_v1
Revises: rag_progress_v1
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "doc_kg_v1"
down_revision: Union[str, None] = "rag_progress_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL 的 ALTER TYPE ... ADD VALUE 不能在事务中执行，需要先手动 COMMIT
    op.execute("COMMIT")
    op.execute(
        "ALTER TYPE agenttasktype ADD VALUE IF NOT EXISTS"
        " 'GENERATE_KNOWLEDGE_GRAPH_FROM_DOCUMENTS'"
    )


def downgrade() -> None:
    # Cannot remove enum values in PostgreSQL
    pass
