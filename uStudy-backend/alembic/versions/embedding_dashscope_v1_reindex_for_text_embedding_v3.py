"""Re-index embeddings for DashScope text-embedding-v3 migration

Clears all existing document chunk embeddings and resets processing tasks
to PENDING so they will be re-embedded with the new model.
Also clears vector memories since the embedding space is incompatible
between qwen3-embedding-8b (OpenRouter) and text-embedding-v3 (DashScope).

Revision ID: embedding_dashscope_v1
Revises: mcp_services_v1
Create Date: 2026-04-17

"""
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "embedding_dashscope_v1"
down_revision: Union[str, None] = "mcp_services_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 清空文档块的 embedding（设为 NULL，触发重新向量化）
    op.execute("UPDATE document_chunks SET embedding = NULL")

    # 2. 将所有已完成的文档处理任务重置为 pending（触发重新处理 + 向量化）
    op.execute(
        "UPDATE document_processing_tasks SET status = 'pending' "
        "WHERE status IN ('completed', 'failed')"
    )

    # 3. 清空 vector_memories（向量空间不兼容，新对话会自动重新生成）
    op.execute("DELETE FROM vector_memories")


def downgrade() -> None:
    # 无法恢复已删除的 embeddings 和记忆数据
    pass
