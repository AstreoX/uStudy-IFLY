"""add learning_path_events table

Revision ID: path_events_v1
Revises: app_usage_v1
Create Date: 2026-02-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "path_events_v1"
down_revision: Union[str, None] = "app_usage_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "learning_path_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "space_id",
            UUID(as_uuid=True),
            sa.ForeignKey("spaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("new_node_names", JSONB, nullable=False),
        sa.Column("trigger_info", JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_learning_path_events_space_id",
        "learning_path_events",
        ["space_id"],
    )
    op.create_index(
        "ix_learning_path_events_user_id",
        "learning_path_events",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_learning_path_events_user_id", table_name="learning_path_events")
    op.drop_index("ix_learning_path_events_space_id", table_name="learning_path_events")
    op.drop_table("learning_path_events")
