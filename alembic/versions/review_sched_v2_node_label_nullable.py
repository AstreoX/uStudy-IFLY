"""review_schedules: node_label nullable for activity-level granularity

Revision ID: review_sched_v2
Revises: path_events_v1
Create Date: 2026-02-20 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "review_sched_v2"
down_revision: Union[str, None] = "path_events_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make node_label nullable — new records use activity-level granularity."""
    op.alter_column(
        "review_schedules",
        "node_label",
        existing_type=sa.String(length=200),
        nullable=True,
    )


def downgrade() -> None:
    """Revert node_label to NOT NULL (old rows with NULL will need manual fix)."""
    op.alter_column(
        "review_schedules",
        "node_label",
        existing_type=sa.String(length=200),
        nullable=False,
    )
