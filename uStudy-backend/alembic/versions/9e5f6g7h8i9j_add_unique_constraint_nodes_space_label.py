"""add unique constraint to nodes (space_id, label)

Revision ID: 9e5f6g7h8i9j
Revises: f668848d6447
Create Date: 2026-02-04 10:30:00.000000

IMPORTANT: Run cleanup_duplicate_nodes.py --execute before this migration!
This migration will fail if duplicate nodes exist.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "9e5f6g7h8i9j"
down_revision: Union[str, Sequence[str], None] = "f668848d6447"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraint on (space_id, label) for nodes table."""
    # Check for duplicates before applying constraint
    connection = op.get_bind()
    result = connection.execute(
        text(
            """
            SELECT COUNT(*) FROM (
                SELECT space_id, label FROM nodes
                GROUP BY space_id, label
                HAVING COUNT(*) > 1
            ) duplicates
            """
        )
    )
    count = result.scalar()

    if count and count > 0:
        raise Exception(
            f"Cannot apply migration: {count} duplicate node group(s) exist. "
            "Run 'python -m scripts.cleanup_duplicate_nodes --execute' first."
        )

    op.create_unique_constraint(
        "uq_nodes_space_label", "nodes", ["space_id", "label"]
    )


def downgrade() -> None:
    """Remove unique constraint from nodes table."""
    op.drop_constraint("uq_nodes_space_label", "nodes", type_="unique")
