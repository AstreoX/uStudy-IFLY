"""Add collaborative learning spaces support

- New tables: space_members, node_user_mastery
- New columns: spaces.is_collaborative, edges.user_id, space_share_codes.share_mode
- New enums: spacememberrole, sharemode
- Data migration: seed space_members OWNER rows for all existing spaces
- Replace uq_edges_unique with two partial indexes

Revision ID: collab_v1
Revises: share_v1
Create Date: 2026-03-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "collab_v1"
down_revision: Union[str, Sequence[str], None] = "share_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create enums
    conn.execute(sa.text(
        "DO $$ BEGIN "
        "  CREATE TYPE spacememberrole AS ENUM ('owner', 'member'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    ))
    conn.execute(sa.text(
        "DO $$ BEGIN "
        "  CREATE TYPE sharemode AS ENUM ('clone', 'collaborative'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    ))

    # 2. Add is_collaborative to spaces
    conn.execute(sa.text("""
        ALTER TABLE spaces
        ADD COLUMN IF NOT EXISTS is_collaborative BOOLEAN NOT NULL DEFAULT false;
    """))

    # 3. Add user_id to edges
    conn.execute(sa.text("""
        ALTER TABLE edges
        ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_edges_user_id ON edges(user_id);"
    ))

    # 4. Replace uq_edges_unique with two partial unique indexes
    # Drop old unique constraint (may fail if it doesn't exist, ignore)
    conn.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE edges DROP CONSTRAINT IF EXISTS uq_edges_unique;
        EXCEPTION WHEN undefined_object THEN NULL;
        END $$;
    """))
    # Shared edges (user_id IS NULL): unique per (space, from, to, type)
    conn.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_edges_shared
        ON edges(space_id, from_node_id, to_node_id, type)
        WHERE user_id IS NULL;
    """))
    # Per-user edges (user_id IS NOT NULL): unique per (space, from, to, type, user)
    conn.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_edges_per_user
        ON edges(space_id, from_node_id, to_node_id, type, user_id)
        WHERE user_id IS NOT NULL;
    """))

    # 5. Add share_mode to space_share_codes
    conn.execute(sa.text("""
        ALTER TABLE space_share_codes
        ADD COLUMN IF NOT EXISTS share_mode sharemode NOT NULL DEFAULT 'clone';
    """))
    # Drop old unique constraint on space_id (was UNIQUE on column)
    conn.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE space_share_codes DROP CONSTRAINT IF EXISTS space_share_codes_space_id_key;
        EXCEPTION WHEN undefined_object THEN NULL;
        END $$;
    """))
    # Add new unique constraint: one code per (space_id, share_mode)
    conn.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE space_share_codes
            ADD CONSTRAINT uq_share_code_space_mode UNIQUE (space_id, share_mode);
        EXCEPTION WHEN duplicate_table THEN NULL;
        END $$;
    """))

    # 6. Create space_members table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS space_members (
            id UUID NOT NULL PRIMARY KEY,
            space_id UUID NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role spacememberrole NOT NULL,
            joined_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            CONSTRAINT uq_space_member UNIQUE (space_id, user_id)
        );
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_space_members_space_id ON space_members(space_id);"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_space_members_user_id ON space_members(user_id);"
    ))

    # 7. Create node_user_mastery table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS node_user_mastery (
            id UUID NOT NULL PRIMARY KEY,
            node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            mastery INTEGER NOT NULL DEFAULT 0 CHECK (mastery >= 0 AND mastery <= 100),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            CONSTRAINT uq_node_user_mastery UNIQUE (node_id, user_id)
        );
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_node_user_mastery_node_id ON node_user_mastery(node_id);"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_node_user_mastery_user_id ON node_user_mastery(user_id);"
    ))

    # 8. Data migration: seed space_members with OWNER for all existing spaces
    conn.execute(sa.text("""
        INSERT INTO space_members (id, space_id, user_id, role)
        SELECT gen_random_uuid(), s.id, s.user_id, 'owner'
        FROM spaces s
        WHERE NOT EXISTS (
            SELECT 1 FROM space_members sm
            WHERE sm.space_id = s.id AND sm.user_id = s.user_id
        );
    """))

    # 9. Copy Node.mastery into node_user_mastery for existing owners
    conn.execute(sa.text("""
        INSERT INTO node_user_mastery (id, node_id, user_id, mastery)
        SELECT gen_random_uuid(), n.id, s.user_id, n.mastery
        FROM nodes n
        JOIN spaces s ON s.id = n.space_id
        WHERE n.mastery IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM node_user_mastery num
            WHERE num.node_id = n.id AND num.user_id = s.user_id
        );
    """))


def downgrade() -> None:
    conn = op.get_bind()

    # Drop new tables
    conn.execute(sa.text("DROP TABLE IF EXISTS node_user_mastery;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS space_members;"))

    # Remove share_mode from space_share_codes
    conn.execute(sa.text("""
        ALTER TABLE space_share_codes DROP CONSTRAINT IF EXISTS uq_share_code_space_mode;
    """))
    conn.execute(sa.text("""
        ALTER TABLE space_share_codes DROP COLUMN IF EXISTS share_mode;
    """))
    # Re-add old unique on space_id
    conn.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE space_share_codes ADD CONSTRAINT space_share_codes_space_id_key UNIQUE (space_id);
        EXCEPTION WHEN duplicate_table THEN NULL;
        END $$;
    """))

    # Restore old edges unique constraint
    conn.execute(sa.text("DROP INDEX IF EXISTS uq_edges_shared;"))
    conn.execute(sa.text("DROP INDEX IF EXISTS uq_edges_per_user;"))
    conn.execute(sa.text("""
        ALTER TABLE edges DROP COLUMN IF EXISTS user_id;
    """))
    conn.execute(sa.text("""
        DO $$ BEGIN
            ALTER TABLE edges ADD CONSTRAINT uq_edges_unique
            UNIQUE (space_id, from_node_id, to_node_id, type);
        EXCEPTION WHEN duplicate_table THEN NULL;
        END $$;
    """))

    # Remove is_collaborative from spaces
    conn.execute(sa.text("ALTER TABLE spaces DROP COLUMN IF EXISTS is_collaborative;"))

    # Drop enums
    conn.execute(sa.text("DROP TYPE IF EXISTS sharemode;"))
    conn.execute(sa.text("DROP TYPE IF EXISTS spacememberrole;"))
