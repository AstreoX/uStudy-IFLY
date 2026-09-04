"""merge primary chat/schema heads

Revision ID: merge_heads_v1
Revises: folders_v1, message_response_status_v1
Create Date: 2026-03-23 00:10:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "merge_heads_v1"
down_revision: Union[str, Sequence[str], None] = ("folders_v1", "message_response_status_v1")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
