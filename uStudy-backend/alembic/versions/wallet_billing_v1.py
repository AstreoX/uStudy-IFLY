"""Add wallet billing and usage charge fields

Revision ID: wallet_billing_v1
Revises: merge_all_v2
Create Date: 2026-04-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "wallet_billing_v1"
down_revision: Union[str, Sequence[str], None] = "merge_all_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE wallettransactiontype AS ENUM (
                'CREDIT_PURCHASE',
                'LLM_CHARGE',
                'SUBSCRIPTION_GRANT',
                'REGISTRATION_GRANT',
                'ADMIN_ADJUSTMENT',
                'REFUND'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
        """
    )
    wallet_tx_type = postgresql.ENUM(
        "CREDIT_PURCHASE",
        "LLM_CHARGE",
        "SUBSCRIPTION_GRANT",
        "REGISTRATION_GRANT",
        "ADMIN_ADJUSTMENT",
        "REFUND",
        name="wallettransactiontype",
        create_type=False,
    )

    op.create_table(
        "wallet_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("balance_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("debt_limit_cents", sa.Integer(), server_default="500", nullable=False),
        sa.Column("total_recharged_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_granted_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_spent_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_wallet_accounts_user_id", "wallet_accounts", ["user_id"], unique=True)

    op.create_table(
        "wallet_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_type", wallet_tx_type, nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("balance_after_cents", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("reference_type", sa.String(length=50), nullable=True),
        sa.Column("reference_id", sa.String(length=100), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["wallet_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_wallet_transactions_user_created", "wallet_transactions", ["user_id", "created_at"], unique=False)
    op.create_index("ix_wallet_transactions_type", "wallet_transactions", ["transaction_type"], unique=False)
    op.create_index("ix_wallet_transactions_idempotency_key", "wallet_transactions", ["idempotency_key"], unique=True)

    op.add_column("payment_orders", sa.Column("product_type", sa.String(length=32), server_default="subscription", nullable=False))
    op.add_column("payment_orders", sa.Column("product_code", sa.String(length=64), nullable=True))
    op.add_column("payment_orders", sa.Column("credit_amount_cents", sa.Integer(), server_default="0", nullable=False))
    op.add_column("payment_orders", sa.Column("wallet_grant_cents", sa.Integer(), server_default="0", nullable=False))
    op.alter_column("payment_orders", "target_tier", existing_type=sa.Enum(name="subscriptiontier"), nullable=True)
    op.alter_column("payment_orders", "billing_cycle", existing_type=postgresql.ENUM(name="billingcycle"), nullable=True)
    op.alter_column("payment_orders", "subscription_days", existing_type=sa.Integer(), server_default="0", nullable=False)
    op.create_index("ix_payment_orders_product_type", "payment_orders", ["product_type"], unique=False)

    op.add_column("payment_qr_codes", sa.Column("product_type", sa.String(length=32), server_default="subscription", nullable=False))
    op.add_column("payment_qr_codes", sa.Column("product_code", sa.String(length=64), nullable=True))
    op.execute("UPDATE payment_qr_codes SET product_code = tier::text || '_' || billing_cycle::text WHERE product_code IS NULL")
    op.drop_constraint("uq_payment_qr_combo", "payment_qr_codes", type_="unique")
    op.alter_column("payment_qr_codes", "tier", existing_type=sa.Enum(name="subscriptiontier"), nullable=True)
    op.alter_column("payment_qr_codes", "billing_cycle", existing_type=postgresql.ENUM(name="billingcycle"), nullable=True)
    op.create_unique_constraint(
        "uq_payment_qr_subscription_combo",
        "payment_qr_codes",
        ["product_type", "tier", "billing_cycle", "pay_method"],
    )
    op.create_unique_constraint(
        "uq_payment_qr_product_combo",
        "payment_qr_codes",
        ["product_type", "product_code", "pay_method"],
    )

    op.alter_column("api_usage_logs", "user_id", nullable=True)
    op.drop_constraint("api_usage_logs_user_id_fkey", "api_usage_logs", type_="foreignkey")
    op.create_foreign_key(
        "api_usage_logs_user_id_fkey",
        "api_usage_logs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("api_usage_logs", sa.Column("source_module", sa.String(length=80), nullable=True))
    op.add_column("api_usage_logs", sa.Column("source_operation", sa.String(length=120), nullable=True))
    op.add_column("api_usage_logs", sa.Column("billable", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("api_usage_logs", sa.Column("charge_cents", sa.Integer(), server_default="0", nullable=False))
    op.add_column("api_usage_logs", sa.Column("billing_status", sa.String(length=32), server_default="not_charged", nullable=False))
    op.add_column("api_usage_logs", sa.Column("wallet_transaction_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("api_usage_logs", sa.Column("idempotency_key", sa.String(length=160), nullable=True))
    op.create_foreign_key(
        "api_usage_logs_wallet_transaction_id_fkey",
        "api_usage_logs",
        "wallet_transactions",
        ["wallet_transaction_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_api_usage_logs_source", "api_usage_logs", ["source_module", "source_operation"], unique=False)
    op.create_index("ix_api_usage_logs_idempotency_key", "api_usage_logs", ["idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_api_usage_logs_idempotency_key", table_name="api_usage_logs")
    op.drop_index("ix_api_usage_logs_source", table_name="api_usage_logs")
    op.drop_constraint("api_usage_logs_wallet_transaction_id_fkey", "api_usage_logs", type_="foreignkey")
    op.drop_column("api_usage_logs", "idempotency_key")
    op.drop_column("api_usage_logs", "wallet_transaction_id")
    op.drop_column("api_usage_logs", "billing_status")
    op.drop_column("api_usage_logs", "charge_cents")
    op.drop_column("api_usage_logs", "billable")
    op.drop_column("api_usage_logs", "source_operation")
    op.drop_column("api_usage_logs", "source_module")
    op.drop_constraint("api_usage_logs_user_id_fkey", "api_usage_logs", type_="foreignkey")
    op.create_foreign_key(
        "api_usage_logs_user_id_fkey",
        "api_usage_logs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("api_usage_logs", "user_id", nullable=False)

    op.drop_constraint("uq_payment_qr_product_combo", "payment_qr_codes", type_="unique")
    op.drop_constraint("uq_payment_qr_subscription_combo", "payment_qr_codes", type_="unique")
    op.alter_column("payment_qr_codes", "billing_cycle", existing_type=postgresql.ENUM(name="billingcycle"), nullable=False)
    op.alter_column("payment_qr_codes", "tier", existing_type=sa.Enum(name="subscriptiontier"), nullable=False)
    op.create_unique_constraint("uq_payment_qr_combo", "payment_qr_codes", ["tier", "billing_cycle", "pay_method"])
    op.drop_column("payment_qr_codes", "product_code")
    op.drop_column("payment_qr_codes", "product_type")

    op.drop_index("ix_payment_orders_product_type", table_name="payment_orders")
    op.alter_column("payment_orders", "subscription_days", existing_type=sa.Integer(), server_default=None, nullable=False)
    op.alter_column("payment_orders", "billing_cycle", existing_type=postgresql.ENUM(name="billingcycle"), nullable=False)
    op.alter_column("payment_orders", "target_tier", existing_type=sa.Enum(name="subscriptiontier"), nullable=False)
    op.drop_column("payment_orders", "wallet_grant_cents")
    op.drop_column("payment_orders", "credit_amount_cents")
    op.drop_column("payment_orders", "product_code")
    op.drop_column("payment_orders", "product_type")

    op.drop_index("ix_wallet_transactions_idempotency_key", table_name="wallet_transactions")
    op.drop_index("ix_wallet_transactions_type", table_name="wallet_transactions")
    op.drop_index("ix_wallet_transactions_user_created", table_name="wallet_transactions")
    op.drop_table("wallet_transactions")
    op.drop_index("ix_wallet_accounts_user_id", table_name="wallet_accounts")
    op.drop_table("wallet_accounts")
    postgresql.ENUM(name="wallettransactiontype").drop(op.get_bind(), checkfirst=True)
