"""Add durable PDF Agentic RAG visual indexes.

Revision ID: pdf_agentic_rag_v1
Revises: assignments_oj_v1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "pdf_agentic_rag_v1"
down_revision: str | None = "assignments_oj_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def upgrade() -> None:
    # Extend the existing one-row-per-document task without invalidating
    # legacy rows. A reprocess increments generation on the same durable row.
    op.add_column(
        "document_processing_tasks",
        sa.Column("generation", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "document_processing_tasks",
        sa.Column("stage", sa.String(40), server_default="queued", nullable=False),
    )
    op.add_column(
        "document_processing_tasks",
        sa.Column("page_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_processing_tasks",
        sa.Column("processed_pages", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "document_processing_tasks",
        sa.Column("asset_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "document_processing_tasks",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "document_processing_tasks",
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "document_processing_tasks",
        sa.Column("lease_owner", sa.String(255), nullable=True),
    )
    op.add_column(
        "document_processing_tasks", sa.Column("lease_token", UUID, nullable=True)
    )
    op.add_column(
        "document_processing_tasks",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "document_processing_tasks",
        sa.Column("error_code", sa.String(64), nullable=True),
    )
    op.add_column(
        "document_processing_tasks",
        sa.Column("warning_code", sa.String(64), nullable=True),
    )
    op.add_column(
        "document_processing_tasks",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_doc_processing_claim",
        "document_processing_tasks",
        ["status", "available_at", "lease_expires_at"],
    )
    op.create_check_constraint(
        "ck_doc_processing_generation", "document_processing_tasks", "generation >= 1"
    )
    op.create_check_constraint(
        "ck_doc_processing_processed_pages",
        "document_processing_tasks",
        "processed_pages >= 0",
    )
    op.create_check_constraint(
        "ck_doc_processing_asset_count", "document_processing_tasks", "asset_count >= 0"
    )
    op.create_check_constraint(
        "ck_doc_processing_attempt_count",
        "document_processing_tasks",
        "attempt_count >= 0",
    )

    # Rows created by the pre-lease worker need an explicit stage. More
    # importantly, a legacy `processing` row has no lease expiry and would
    # never satisfy the new recovery query (`lease_expires_at < now()`). Requeue
    # those rows once during deployment so the durable worker can claim them.
    op.execute(
        """
        UPDATE document_processing_tasks
        SET stage = CASE
            WHEN status = 'completed' THEN 'completed'
            WHEN status = 'failed' THEN 'failed'
            ELSE 'queued'
        END
        """
    )
    op.execute(
        """
        UPDATE document_processing_tasks
        SET status = 'pending',
            stage = 'queued',
            available_at = now(),
            started_at = NULL,
            completed_at = NULL,
            error_message = NULL,
            error_code = NULL,
            lease_owner = NULL,
            lease_token = NULL,
            lease_expires_at = NULL
        WHERE status = 'processing'
        """
    )

    op.create_table(
        "pdf_visual_indexes",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "document_id",
            UUID,
            sa.ForeignKey("space_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "space_id",
            UUID,
            sa.ForeignKey("spaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), server_default="staging", nullable=False),
        sa.Column(
            "is_current", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column(
            "outline_status", sa.String(20), server_default="pending", nullable=False
        ),
        sa.Column("toc_pdf_page_start", sa.Integer(), nullable=True),
        sa.Column("toc_pdf_page_end", sa.Integer(), nullable=True),
        sa.Column("page_offset", sa.Integer(), nullable=True),
        sa.Column(
            "outline_entries",
            JSONB,
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("outline_markdown_path", sa.String(1024), nullable=True),
        sa.Column("derived_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("renderer_version", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("generation >= 1", name="ck_pdf_visual_indexes_generation"),
        sa.CheckConstraint("page_count >= 1", name="ck_pdf_visual_indexes_page_count"),
        sa.CheckConstraint(
            "derived_bytes >= 0", name="ck_pdf_visual_indexes_derived_bytes"
        ),
        sa.CheckConstraint(
            "state IN ('staging', 'published', 'superseded', 'failed')",
            name="ck_pdf_visual_indexes_state",
        ),
        sa.CheckConstraint(
            "outline_status IN ('pending', 'ready', 'not_found', 'failed')",
            name="ck_pdf_visual_indexes_outline_status",
        ),
        sa.CheckConstraint(
            "toc_pdf_page_start IS NULL OR toc_pdf_page_start >= 1",
            name="ck_pdf_visual_indexes_toc_start",
        ),
        sa.CheckConstraint(
            "toc_pdf_page_end IS NULL OR toc_pdf_page_end >= toc_pdf_page_start",
            name="ck_pdf_visual_indexes_toc_end",
        ),
        sa.UniqueConstraint(
            "document_id",
            "generation",
            name="uq_pdf_visual_indexes_document_generation",
        ),
    )
    op.create_index("ix_pdf_visual_indexes_space", "pdf_visual_indexes", ["space_id"])
    op.create_index("ix_pdf_visual_indexes_state", "pdf_visual_indexes", ["state"])
    op.create_index(
        "uq_pdf_visual_indexes_current_document",
        "pdf_visual_indexes",
        ["document_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )

    op.create_table(
        "pdf_page_assets",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "index_id",
            UUID,
            sa.ForeignKey("pdf_visual_indexes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            UUID,
            sa.ForeignKey("space_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "space_id",
            UUID,
            sa.ForeignKey("spaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pages_per_image", sa.Integer(), nullable=False),
        sa.Column("physical_page_start", sa.Integer(), nullable=False),
        sa.Column("physical_page_end", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "pages_per_image IN (1, 2, 4)", name="ck_pdf_page_assets_pages_per_image"
        ),
        sa.CheckConstraint(
            "physical_page_start >= 1", name="ck_pdf_page_assets_page_start"
        ),
        sa.CheckConstraint(
            "physical_page_end >= physical_page_start",
            name="ck_pdf_page_assets_page_end",
        ),
        sa.CheckConstraint("width > 0", name="ck_pdf_page_assets_width"),
        sa.CheckConstraint("height > 0", name="ck_pdf_page_assets_height"),
        sa.CheckConstraint("byte_size > 0", name="ck_pdf_page_assets_byte_size"),
        sa.UniqueConstraint(
            "index_id",
            "pages_per_image",
            "physical_page_start",
            name="uq_pdf_page_assets_index_lod_start",
        ),
    )
    op.create_index("ix_pdf_page_assets_document", "pdf_page_assets", ["document_id"])
    op.create_index("ix_pdf_page_assets_space", "pdf_page_assets", ["space_id"])

    op.create_table(
        "pdf_index_agent_calls",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "index_id",
            UUID,
            sa.ForeignKey("pdf_visual_indexes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("call_key", sa.String(512), nullable=False, unique=True),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("response_data", JSONB, nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("round_index >= 0", name="ck_pdf_index_agent_calls_round"),
    )
    op.create_index(
        "ix_pdf_index_agent_calls_index", "pdf_index_agent_calls", ["index_id"]
    )

    op.add_column(
        "document_chunks", sa.Column("pdf_visual_index_id", UUID, nullable=True)
    )
    op.add_column(
        "document_chunks", sa.Column("chunk_kind", sa.String(32), nullable=True)
    )
    op.add_column(
        "document_chunks", sa.Column("physical_page_start", sa.Integer(), nullable=True)
    )
    op.add_column(
        "document_chunks", sa.Column("physical_page_end", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_document_chunks_pdf_visual_index",
        "document_chunks",
        "pdf_visual_indexes",
        ["pdf_visual_index_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_document_chunks_pdf_visual_index_id",
        "document_chunks",
        ["pdf_visual_index_id"],
    )
    op.create_index(
        "ix_document_chunks_kind_page",
        "document_chunks",
        ["chunk_kind", "physical_page_start"],
    )
    op.create_check_constraint(
        "ck_document_chunks_chunk_kind",
        "document_chunks",
        "chunk_kind IS NULL OR chunk_kind IN ('native_page', 'outline_entry')",
    )
    op.create_check_constraint(
        "ck_document_chunks_page_start",
        "document_chunks",
        "physical_page_start IS NULL OR physical_page_start >= 1",
    )
    op.create_check_constraint(
        "ck_document_chunks_page_end",
        "document_chunks",
        "physical_page_end IS NULL OR physical_page_end >= physical_page_start",
    )


def downgrade() -> None:
    op.drop_constraint("ck_document_chunks_page_end", "document_chunks", type_="check")
    op.drop_constraint(
        "ck_document_chunks_page_start", "document_chunks", type_="check"
    )
    op.drop_constraint(
        "ck_document_chunks_chunk_kind", "document_chunks", type_="check"
    )
    op.drop_index("ix_document_chunks_kind_page", table_name="document_chunks")
    op.drop_index(
        "ix_document_chunks_pdf_visual_index_id", table_name="document_chunks"
    )
    op.drop_constraint(
        "fk_document_chunks_pdf_visual_index", "document_chunks", type_="foreignkey"
    )
    op.drop_column("document_chunks", "physical_page_end")
    op.drop_column("document_chunks", "physical_page_start")
    op.drop_column("document_chunks", "chunk_kind")
    op.drop_column("document_chunks", "pdf_visual_index_id")

    op.drop_table("pdf_index_agent_calls")
    op.drop_table("pdf_page_assets")
    op.drop_table("pdf_visual_indexes")

    op.drop_constraint(
        "ck_doc_processing_attempt_count", "document_processing_tasks", type_="check"
    )
    op.drop_constraint(
        "ck_doc_processing_asset_count", "document_processing_tasks", type_="check"
    )
    op.drop_constraint(
        "ck_doc_processing_processed_pages",
        "document_processing_tasks",
        type_="check",
    )
    op.drop_constraint(
        "ck_doc_processing_generation", "document_processing_tasks", type_="check"
    )
    op.drop_index("ix_doc_processing_claim", table_name="document_processing_tasks")
    op.drop_column("document_processing_tasks", "updated_at")
    op.drop_column("document_processing_tasks", "warning_code")
    op.drop_column("document_processing_tasks", "error_code")
    op.drop_column("document_processing_tasks", "lease_expires_at")
    op.drop_column("document_processing_tasks", "lease_token")
    op.drop_column("document_processing_tasks", "lease_owner")
    op.drop_column("document_processing_tasks", "available_at")
    op.drop_column("document_processing_tasks", "attempt_count")
    op.drop_column("document_processing_tasks", "asset_count")
    op.drop_column("document_processing_tasks", "processed_pages")
    op.drop_column("document_processing_tasks", "page_count")
    op.drop_column("document_processing_tasks", "stage")
    op.drop_column("document_processing_tasks", "generation")
