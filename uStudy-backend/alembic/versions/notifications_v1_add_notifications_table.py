"""add notifications table for in-app notifications

Revision ID: notifications_v1
Revises: review_sm2_v1
Create Date: 2026-03-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "notifications_v1"
down_revision: Union[str, None] = "review_sm2_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type idempotently via raw SQL (avoids sa.Enum checkfirst issues with async PG)
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notificationtype') THEN
                CREATE TYPE notificationtype AS ENUM (
                    'REVIEW_QUIZ_READY', 'REVIEW_REMINDER',
                    'INACTIVITY_CARE', 'SYSTEM_ANNOUNCEMENT'
                );
            END IF;
        END$$;
    """))

    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "type",
            PG_ENUM(
                "REVIEW_QUIZ_READY",
                "REVIEW_REMINDER",
                "INACTIVITY_CARE",
                "SYSTEM_ANNOUNCEMENT",
                name="notificationtype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("data", JSONB, nullable=True),
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "idx_notif_user_read_created",
        "notifications",
        ["user_id", "is_read", "created_at"],
    )
    op.create_index(
        "idx_notif_user_created",
        "notifications",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_notif_user_created", table_name="notifications")
    op.drop_index("idx_notif_user_read_created", table_name="notifications")
    op.drop_table("notifications")

    sa.Enum(name="notificationtype").drop(op.get_bind(), checkfirst=True)
