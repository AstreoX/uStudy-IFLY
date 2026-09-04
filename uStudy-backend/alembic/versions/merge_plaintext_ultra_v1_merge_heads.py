"""Merge plaintext_rag_v2 and ultra_tier_v1 heads into single head

Revision ID: merge_plaintext_ultra_v1
Revises: plaintext_rag_v2, ultra_tier_v1
Create Date: 2026-04-21
"""

from typing import Sequence, Union

from alembic import op

revision: str = "merge_plaintext_ultra_v1"
down_revision: Union[str, Sequence[str], None] = ("plaintext_rag_v2", "ultra_tier_v1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
