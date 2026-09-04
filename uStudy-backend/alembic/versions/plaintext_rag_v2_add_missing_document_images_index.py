"""Add missing ix_document_images_document_id index

Revision ID: plaintext_rag_v2
Revises: plaintext_rag_v1
Create Date: 2026-04-21
"""

from typing import Sequence, Union

from alembic import op

revision: str = "plaintext_rag_v2"
down_revision: Union[str, None] = "plaintext_rag_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_document_images_document_id", "document_images", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_document_images_document_id", table_name="document_images")
