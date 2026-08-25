"""add payment_orders table

Revision ID: payment_v1
Revises: p1q2r3s4t5u6
Create Date: 2026-02-23 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, UUID

# revision identifiers, used by Alembic.
revision: str = "payment_v1"
down_revision: Union[str, None] = "p1q2r3s4t5u6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types idempotently via raw SQL
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'orderstatus') THEN
                CREATE TYPE orderstatus AS ENUM ('pending', 'paid', 'expired', 'cancelled');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'billingcycle') THEN
                CREATE TYPE billingcycle AS ENUM ('monthly', 'semester', 'yearly');
            END IF;
        END$$;
    """))

    # Create payment_orders table
    op.create_table(
        "payment_orders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("out_trade_no", sa.String(64), unique=True, nullable=False),
        sa.Column(
            "target_tier",
            ENUM("FREE", "BASIC", "PREMIUM", "ALPHA", name="subscriptiontier", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "billing_cycle",
            ENUM("monthly", "semester", "yearly", name="billingcycle", create_type=False),
            nullable=False,
        ),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("subscription_days", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            ENUM("pending", "paid", "expired", "cancelled", name="orderstatus", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("alipay_trade_no", sa.String(64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Create indexes
    op.create_index("ix_payment_orders_user_id", "payment_orders", ["user_id"])
    op.create_index("ix_payment_orders_out_trade_no", "payment_orders", ["out_trade_no"], unique=True)
    op.create_index("ix_payment_orders_status", "payment_orders", ["status"])
    op.create_index("ix_payment_orders_expires_at", "payment_orders", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_payment_orders_expires_at", table_name="payment_orders")
    op.drop_index("ix_payment_orders_status", table_name="payment_orders")
    op.drop_index("ix_payment_orders_out_trade_no", table_name="payment_orders")
    op.drop_index("ix_payment_orders_user_id", table_name="payment_orders")
    op.drop_table("payment_orders")

    sa.Enum(name="billingcycle").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="orderstatus").drop(op.get_bind(), checkfirst=True)
