"""Add private note, quiz, and folder ownership metadata.

Revision ID: private_content_acl_v1
Revises: pdf_agentic_rag_v1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "private_content_acl_v1"
down_revision: str | None = "pdf_agentic_rag_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column(
        "notes",
        sa.Column("visibility", sa.String(16), server_default="shared", nullable=False),
    )
    op.create_check_constraint(
        "ck_notes_visibility",
        "notes",
        "visibility IN ('shared', 'private')",
    )
    op.create_check_constraint(
        "ck_notes_private_creator",
        "notes",
        "visibility = 'shared' OR creator_user_id IS NOT NULL",
    )

    op.add_column("quizzes", sa.Column("creator_user_id", UUID, nullable=True))
    op.add_column(
        "quizzes",
        sa.Column("visibility", sa.String(16), server_default="shared", nullable=False),
    )
    op.create_foreign_key(
        "fk_quizzes_creator_user_id",
        "quizzes",
        "users",
        ["creator_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_quizzes_creator_user_id", "quizzes", ["creator_user_id"])
    op.create_check_constraint(
        "ck_quizzes_visibility",
        "quizzes",
        "visibility IN ('shared', 'private')",
    )
    op.create_check_constraint(
        "ck_quizzes_private_creator",
        "quizzes",
        "visibility = 'shared' OR creator_user_id IS NOT NULL",
    )

    op.add_column("folders", sa.Column("creator_user_id", UUID, nullable=True))
    op.add_column(
        "folders",
        sa.Column("visibility", sa.String(16), server_default="shared", nullable=False),
    )
    op.create_foreign_key(
        "fk_folders_creator_user_id",
        "folders",
        "users",
        ["creator_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_folders_creator_user_id", "folders", ["creator_user_id"])
    op.create_check_constraint(
        "ck_folders_visibility",
        "folders",
        "visibility IN ('shared', 'private')",
    )
    op.create_check_constraint(
        "ck_folders_private_creator",
        "folders",
        "visibility = 'shared' OR creator_user_id IS NOT NULL",
    )


def downgrade() -> None:
    bind = op.get_bind()
    private_rows = sum(
        bind.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE visibility = 'private'")
        ).scalar_one()
        for table in ("notes", "quizzes", "folders")
    )
    if private_rows:
        raise RuntimeError(
            "refusing to downgrade private-content ACL while private rows exist; "
            "rollback the course data or restore the pre-migration backup first"
        )

    op.drop_constraint("ck_folders_private_creator", "folders", type_="check")
    op.drop_constraint("ck_folders_visibility", "folders", type_="check")
    op.drop_index("ix_folders_creator_user_id", table_name="folders")
    op.drop_constraint("fk_folders_creator_user_id", "folders", type_="foreignkey")
    op.drop_column("folders", "visibility")
    op.drop_column("folders", "creator_user_id")

    op.drop_constraint("ck_quizzes_private_creator", "quizzes", type_="check")
    op.drop_constraint("ck_quizzes_visibility", "quizzes", type_="check")
    op.drop_index("ix_quizzes_creator_user_id", table_name="quizzes")
    op.drop_constraint("fk_quizzes_creator_user_id", "quizzes", type_="foreignkey")
    op.drop_column("quizzes", "visibility")
    op.drop_column("quizzes", "creator_user_id")

    op.drop_constraint("ck_notes_private_creator", "notes", type_="check")
    op.drop_constraint("ck_notes_visibility", "notes", type_="check")
    op.drop_column("notes", "visibility")
