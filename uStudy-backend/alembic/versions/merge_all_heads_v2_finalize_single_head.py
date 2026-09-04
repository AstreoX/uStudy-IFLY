"""final merge of all alembic heads

Revision ID: merge_all_heads_v2
Revises: daily_study_head_anchor_v1, merge_heads_v1
Create Date: 2026-03-23 00:21:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "merge_all_heads_v2"
down_revision: Union[str, Sequence[str], None] = ("daily_study_head_anchor_v1", "merge_heads_v1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
