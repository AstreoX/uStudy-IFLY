"""add teacher presentation agent control-plane tables

Revision ID: teacher_presentations_v1
Revises: teacher_dashboard_v1
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "teacher_presentations_v1"
down_revision: Union[str, None] = "teacher_dashboard_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


conversation_kind = postgresql.ENUM(
    "learning", "teacher_presentation", name="conversationkind", create_type=False
)
revision_status = postgresql.ENUM(
    "draft", "completed", "failed", name="presentationrevisionstatus", create_type=False
)
run_status = postgresql.ENUM(
    "queued", "running", "waiting_confirmation", "completed", "failed", "cancelled",
    name="presentationrunstatus", create_type=False,
)
asset_kind = postgresql.ENUM(
    "source", "template", "generated_image", "preview", "pptx",
    name="presentationassetkind", create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE TYPE conversationkind AS ENUM ('learning', 'teacher_presentation')")
    op.add_column(
        "conversations",
        sa.Column("kind", conversation_kind, server_default="learning", nullable=False),
    )
    op.create_index("ix_conversations_kind", "conversations", ["kind"])

    op.execute("CREATE TYPE presentationrevisionstatus AS ENUM ('draft', 'completed', 'failed')")
    op.execute(
        "CREATE TYPE presentationrunstatus AS ENUM "
        "('queued', 'running', 'waiting_confirmation', 'completed', 'failed', 'cancelled')"
    )
    op.execute(
        "CREATE TYPE presentationassetkind AS ENUM "
        "('source', 'template', 'generated_image', 'preview', 'pptx')"
    )

    op.create_table(
        "teacher_presentation_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("teacher_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("current_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("published_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["published_document_id"], ["space_documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id"),
    )
    op.create_index(
        "ix_teacher_presentation_projects_space_teacher",
        "teacher_presentation_projects", ["space_id", "teacher_user_id"],
    )
    op.create_index(
        "ix_teacher_presentation_projects_current_revision",
        "teacher_presentation_projects", ["current_revision_id"],
    )

    op.create_table(
        "teacher_presentation_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("status", revision_status, server_default="draft", nullable=False),
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("manifest", postgresql.JSONB(), nullable=True),
        sa.Column("pptx_path", sa.String(1024), nullable=True),
        sa.Column("preview_manifest", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["teacher_presentation_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_revision_id"], ["teacher_presentation_revisions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "revision_number", name="uq_presentation_revision_number"),
    )
    op.create_index(
        "ix_teacher_presentation_revisions_project",
        "teacher_presentation_revisions", ["project_id", "created_at"],
    )
    op.create_foreign_key(
        "fk_presentation_project_current_revision",
        "teacher_presentation_projects", "teacher_presentation_revisions",
        ["current_revision_id"], ["id"], ondelete="SET NULL",
    )

    op.create_table(
        "teacher_presentation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("manager_run_id", sa.String(128), nullable=True),
        sa.Column("status", run_status, server_default="queued", nullable=False),
        sa.Column("capability_token_hash", sa.String(64), nullable=False),
        sa.Column("capability_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["teacher_presentation_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revision_id"], ["teacher_presentation_revisions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revision_id"),
        sa.UniqueConstraint("manager_run_id"),
    )
    op.create_index("ix_teacher_presentation_runs_project", "teacher_presentation_runs", ["project_id", "created_at"])
    op.create_index("ix_teacher_presentation_runs_status", "teacher_presentation_runs", ["status"])

    op.create_table(
        "teacher_presentation_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", asset_kind, nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("private_path", sa.String(1024), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("asset_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["teacher_presentation_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revision_id"], ["teacher_presentation_revisions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_teacher_presentation_assets_project", "teacher_presentation_assets", ["project_id", "created_at"])

    op.create_table(
        "teacher_presentation_publications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("publisher_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["teacher_presentation_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["revision_id"], ["teacher_presentation_revisions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["document_id"], ["space_documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["publisher_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_teacher_presentation_publications_project",
        "teacher_presentation_publications", ["project_id", "created_at"],
    )

    op.create_table(
        "teacher_presentation_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["teacher_presentation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_presentation_event_sequence"),
    )
    op.create_index("ix_teacher_presentation_events_run", "teacher_presentation_events", ["run_id", "sequence"])


def downgrade() -> None:
    op.drop_table("teacher_presentation_events")
    op.drop_table("teacher_presentation_publications")
    op.drop_table("teacher_presentation_assets")
    op.drop_table("teacher_presentation_runs")
    op.drop_constraint("fk_presentation_project_current_revision", "teacher_presentation_projects", type_="foreignkey")
    op.drop_table("teacher_presentation_revisions")
    op.drop_table("teacher_presentation_projects")
    op.execute("DROP TYPE presentationassetkind")
    op.execute("DROP TYPE presentationrunstatus")
    op.execute("DROP TYPE presentationrevisionstatus")
    op.drop_index("ix_conversations_kind", table_name="conversations")
    op.drop_column("conversations", "kind")
    op.execute("DROP TYPE conversationkind")
