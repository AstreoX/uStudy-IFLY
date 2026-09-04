"""add payment notify logs table

Revision ID: payment_notify_logs_v1
Revises: review_automation_disabled_v1
Create Date: 2026-05-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "payment_notify_logs_v1"
down_revision: Union[str, Sequence[str], None] = "review_automation_disabled_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_notify_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("out_trade_no", sa.String(length=64), nullable=True),
        sa.Column("trade_no", sa.String(length=64), nullable=True),
        sa.Column("trade_status", sa.String(length=32), nullable=True),
        sa.Column("app_id", sa.String(length=64), nullable=True),
        sa.Column("seller_id", sa.String(length=64), nullable=True),
        sa.Column("total_amount", sa.String(length=32), nullable=True),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("verify_success", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("process_success", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("process_message", sa.String(length=255), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_notify_logs_out_trade_no", "payment_notify_logs", ["out_trade_no"])
    op.create_index("ix_payment_notify_logs_trade_no", "payment_notify_logs", ["trade_no"])
    op.create_index("ix_payment_notify_logs_received_at", "payment_notify_logs", ["received_at"])
    op.create_index("ix_payment_notify_logs_provider_created", "payment_notify_logs", ["provider", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_payment_notify_logs_provider_created", table_name="payment_notify_logs")
    op.drop_index("ix_payment_notify_logs_received_at", table_name="payment_notify_logs")
    op.drop_index("ix_payment_notify_logs_trade_no", table_name="payment_notify_logs")
    op.drop_index("ix_payment_notify_logs_out_trade_no", table_name="payment_notify_logs")
    op.drop_table("payment_notify_logs")
