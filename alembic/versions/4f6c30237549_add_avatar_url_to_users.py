"""add_avatar_url_to_users

Revision ID: 4f6c30237549
Revises: 
Create Date: 2026-01-30 13:29:05.025619

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '4f6c30237549'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum_exists(conn, enum_name: str) -> bool:
    return bool(
        conn.execute(
            sa.text(
                "SELECT 1 FROM pg_type t "
                "JOIN pg_namespace n ON n.oid = t.typnamespace "
                "WHERE t.typname = :name AND n.nspname = current_schema()"
            ),
            {"name": enum_name},
        ).scalar()
    )


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    return bool(
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name = :table_name "
                "AND column_name = :column_name"
            ),
            {"table_name": table_name, "column_name": column_name},
        ).scalar()
    )


def _ensure_legacy_base_schema() -> None:
    """
    Bootstrap legacy core tables for fresh databases.

    Historical project schema was created via create_all before Alembic was introduced.
    This migration is the first Alembic revision, so fresh DBs need these core tables/enums
    before incremental migrations can run.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _enum_exists(bind, "subscriptiontier"):
        op.execute("CREATE TYPE subscriptiontier AS ENUM ('FREE', 'BASIC', 'PREMIUM')")
    if not _enum_exists(bind, "messagerole"):
        op.execute("CREATE TYPE messagerole AS ENUM ('USER', 'ASSISTANT')")
    if not _enum_exists(bind, "edgetype"):
        op.execute("CREATE TYPE edgetype AS ENUM ('KNOWLEDGE_TREE', 'LEARNING_PATH')")
    if not _enum_exists(bind, "verificationcodepurpose"):
        op.execute(
            "CREATE TYPE verificationcodepurpose AS ENUM ('REGISTRATION', 'PASSWORD_RESET')"
        )

    if not inspector.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=True),
            sa.Column("apple_id", sa.String(length=255), nullable=True),
            sa.Column("nickname", sa.String(length=100), nullable=False),
            sa.Column(
                "subscription_tier",
                postgresql.ENUM(
                    "FREE",
                    "BASIC",
                    "PREMIUM",
                    name="subscriptiontier",
                    create_type=False,
                ),
                nullable=False,
                server_default="FREE",
            ),
            sa.Column("subscription_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)
        op.create_index("ix_users_apple_id", "users", ["apple_id"], unique=True)

    if not inspector.has_table("spaces"):
        op.create_table(
            "spaces",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("color", sa.String(length=20), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_spaces_user_id", "spaces", ["user_id"], unique=False)

    if not inspector.has_table("conversations"):
        op.create_table(
            "conversations",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_conversations_user_created",
            "conversations",
            ["user_id", "created_at"],
            unique=False,
        )
        op.create_index(
            "ix_conversations_space_id", "conversations", ["space_id"], unique=False
        )

    if not inspector.has_table("messages"):
        op.create_table(
            "messages",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "role",
                postgresql.ENUM(
                    "USER", "ASSISTANT", name="messagerole", create_type=False
                ),
                nullable=False,
            ),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_messages_conversation_created",
            "messages",
            ["conversation_id", "created_at"],
            unique=False,
        )

    if not inspector.has_table("nodes"):
        op.create_table(
            "nodes",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("label", sa.String(length=200), nullable=False),
            sa.Column("mastery", sa.Integer(), nullable=True),
            sa.CheckConstraint(
                "mastery IS NULL OR (mastery >= 0 AND mastery <= 100)",
                name="ck_nodes_mastery_range",
            ),
            sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_nodes_space_id", "nodes", ["space_id"], unique=False)

    if not inspector.has_table("edges"):
        op.create_table(
            "edges",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("from_node_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("to_node_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "type",
                postgresql.ENUM(
                    "KNOWLEDGE_TREE",
                    "LEARNING_PATH",
                    name="edgetype",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["from_node_id"], ["nodes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["to_node_id"], ["nodes.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "space_id", "from_node_id", "to_node_id", "type", name="uq_edges_unique"
            ),
        )
        op.create_index("ix_edges_space_id", "edges", ["space_id"], unique=False)
        op.create_index("ix_edges_from_node", "edges", ["from_node_id"], unique=False)
        op.create_index("ix_edges_to_node", "edges", ["to_node_id"], unique=False)

    if not inspector.has_table("verification_codes"):
        op.create_table(
            "verification_codes",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("code", sa.String(length=20), nullable=False),
            sa.Column(
                "purpose",
                postgresql.ENUM(
                    "REGISTRATION",
                    "PASSWORD_RESET",
                    name="verificationcodepurpose",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_verification_email_purpose",
            "verification_codes",
            ["email", "purpose"],
            unique=False,
        )

    if not inspector.has_table("refresh_tokens"):
        op.create_table(
            "refresh_tokens",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("device_info", sa.String(length=255), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("replaced_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash"),
        )
        op.create_index(
            "ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False
        )
        op.create_index(
            "ix_refresh_tokens_token_hash",
            "refresh_tokens",
            ["token_hash"],
            unique=False,
        )


def upgrade() -> None:
    """Upgrade schema."""
    _ensure_legacy_base_schema()

    bind = op.get_bind()
    if not _column_exists(bind, "users", "avatar_url"):
        op.add_column(
            "users", sa.Column("avatar_url", sa.String(length=500), nullable=True)
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if _column_exists(bind, "users", "avatar_url"):
        op.drop_column("users", "avatar_url")
