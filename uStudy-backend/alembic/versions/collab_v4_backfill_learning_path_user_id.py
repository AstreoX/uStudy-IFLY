"""collab v4: backfill NULL user_id on learning path edges

Set user_id = space owner for all LEARNING_PATH edges where user_id IS NULL.
These edges were created before per-user data isolation was added.

Revision ID: collab_v4
Revises: collab_v3
Create Date: 2026-03-09

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "collab_v4"
down_revision: Union[str, Sequence[str], None] = "collab_v3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE edges
        SET user_id = spaces.user_id
        FROM spaces
        WHERE edges.space_id = spaces.id
          AND edges.type = 'LEARNING_PATH'
          AND edges.user_id IS NULL
    """)


def downgrade() -> None:
    pass  # Not reversible — setting NULL back would break collaborative filtering
