"""Fix share_mode column type from VARCHAR to sharemode enum

The collab_v1 migration incorrectly created share_mode as VARCHAR(20).
The SQLAlchemy model expects a PostgreSQL native enum type (sharemode).

Revision ID: collab_v2
Revises: collab_v1
Create Date: 2026-03-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "collab_v2"
down_revision: Union[str, Sequence[str], None] = "collab_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Ensure the sharemode enum type exists
    conn.execute(sa.text(
        "DO $$ BEGIN "
        "  CREATE TYPE sharemode AS ENUM ('clone', 'collaborative'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    ))

    # Check if column is VARCHAR and convert to sharemode enum
    # Drop the unique constraint first (it references the column)
    conn.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE space_share_codes DROP CONSTRAINT IF EXISTS uq_share_code_space_mode;
        EXCEPTION WHEN undefined_object THEN NULL;
        END $$;
    """))

    # Drop the VARCHAR default before type conversion
    conn.execute(sa.text("""
        ALTER TABLE space_share_codes
        ALTER COLUMN share_mode DROP DEFAULT;
    """))

    # ALTER column type from VARCHAR to sharemode enum
    conn.execute(sa.text("""
        ALTER TABLE space_share_codes
        ALTER COLUMN share_mode TYPE sharemode USING share_mode::sharemode;
    """))

    # Re-add default as enum value
    conn.execute(sa.text("""
        ALTER TABLE space_share_codes
        ALTER COLUMN share_mode SET DEFAULT 'clone'::sharemode;
    """))

    # Re-add the unique constraint
    conn.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE space_share_codes
            ADD CONSTRAINT uq_share_code_space_mode UNIQUE (space_id, share_mode);
        EXCEPTION WHEN duplicate_table THEN NULL;
        END $$;
    """))


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE space_share_codes DROP CONSTRAINT IF EXISTS uq_share_code_space_mode;
        EXCEPTION WHEN undefined_object THEN NULL;
        END $$;
    """))

    conn.execute(sa.text("""
        ALTER TABLE space_share_codes
        ALTER COLUMN share_mode TYPE VARCHAR(20) USING share_mode::text;
    """))

    conn.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE space_share_codes
            ADD CONSTRAINT uq_share_code_space_mode UNIQUE (space_id, share_mode);
        EXCEPTION WHEN duplicate_table THEN NULL;
        END $$;
    """))
