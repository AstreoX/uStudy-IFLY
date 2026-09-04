"""Merge merge_plaintext_ultra_v1 and embedding_dashscope_v1 into single head

Revision ID: merge_all_v2
Revises: merge_plaintext_ultra_v1, embedding_dashscope_v1
Create Date: 2026-04-21
"""

from typing import Sequence, Union

from alembic import op

revision: str = "merge_all_v2"
down_revision: Union[str, Sequence[str], None] = ("merge_plaintext_ultra_v1", "embedding_dashscope_v1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
