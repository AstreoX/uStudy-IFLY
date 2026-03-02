"""fix subscriptiontier enum alpha case

Revision ID: o4p5q6r7s8t9
Revises: n3o4p5q6r7s8
Create Date: 2026-02-13

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "o4p5q6r7s8t9"
down_revision: Union[str, None] = "n3o4p5q6r7s8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'subscriptiontier' AND e.enumlabel = 'alpha'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'subscriptiontier' AND e.enumlabel = 'ALPHA'
            ) THEN
                ALTER TYPE subscriptiontier RENAME VALUE 'alpha' TO 'ALPHA';
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'subscriptiontier' AND e.enumlabel = 'ALPHA'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'subscriptiontier' AND e.enumlabel = 'alpha'
            ) THEN
                ALTER TYPE subscriptiontier RENAME VALUE 'ALPHA' TO 'alpha';
            END IF;
        END
        $$;
        """
    )
