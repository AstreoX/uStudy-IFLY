"""add quick_chat_llm to usagetype enum

Revision ID: l1m2n3o4p5q6
Revises: k0l1m2n3o4p5
Create Date: 2026-02-13
"""

from typing import Sequence, Union

from alembic import op

revision: str = "l1m2n3o4p5q6"
down_revision: Union[str, None] = "k0l1m2n3o4p5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing enum values to usagetype
    # Must commit current transaction first, then run outside transaction
    op.execute("COMMIT")
    op.execute("ALTER TYPE usagetype ADD VALUE IF NOT EXISTS 'quick_chat_llm'")
    op.execute("ALTER TYPE usagetype ADD VALUE IF NOT EXISTS 'agent_llm'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values directly
    # Would need to recreate the type, which is complex and risky
    pass
