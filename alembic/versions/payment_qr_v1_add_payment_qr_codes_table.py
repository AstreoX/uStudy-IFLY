"""add payment_qr_codes table

Revision ID: payment_qr_v1
Revises: payment_v2
Create Date: 2026-02-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, UUID

# revision identifiers, used by Alembic.
revision: str = "payment_qr_v1"
down_revision: Union[str, None] = "payment_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_qr_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tier", ENUM("FREE", "BASIC", "PREMIUM", "ALPHA", name="subscriptiontier", create_type=False), nullable=False),
        sa.Column("billing_cycle", ENUM("monthly", "semester", "yearly", name="billingcycle", create_type=False), nullable=False),
        sa.Column("pay_method", sa.String(20), nullable=False, comment="alipay / wechat"),
        sa.Column("display_filename", sa.String(255), nullable=False, comment="展示用二维码文件名"),
        sa.Column("save_filename", sa.String(255), nullable=True, comment="保存到相册用文件名"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tier", "billing_cycle", "pay_method", name="uq_payment_qr_combo"),
    )


def downgrade() -> None:
    op.drop_table("payment_qr_codes")
