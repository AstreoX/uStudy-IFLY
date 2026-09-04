"""Add personal invite codes and invite rewards

Revision ID: invite_rewards_v1
Revises: wallet_billing_v1, vec_mem_dim_1024_v1
Create Date: 2026-04-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "invite_rewards_v1"
down_revision: Union[str, Sequence[str], None] = (
    "wallet_billing_v1",
    "vec_mem_dim_1024_v1",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE wallettransactiontype ADD VALUE IF NOT EXISTS 'INVITE_REWARD'")
    op.execute("ALTER TYPE wallettransactiontype ADD VALUE IF NOT EXISTS 'INVITE_SIGNUP_BONUS'")

    op.create_table(
        "invite_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("uses_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_invite_codes_owner_user_id", "invite_codes", ["owner_user_id"], unique=True)
    op.create_index("ix_invite_codes_code", "invite_codes", ["code"], unique=True)
    op.create_index("ix_invite_codes_status", "invite_codes", ["status"], unique=False)

    op.create_table(
        "invite_redemptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invite_code_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inviter_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invitee_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("inviter_reward_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invitee_reward_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("inviter_user_id <> invitee_user_id", name="ck_invite_redemptions_not_self"),
        sa.ForeignKeyConstraint(["invite_code_id"], ["invite_codes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invitee_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invitee_reward_transaction_id"], ["wallet_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["inviter_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inviter_reward_transaction_id"], ["wallet_transactions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invitee_user_id"),
    )
    op.create_index("ix_invite_redemptions_inviter_created", "invite_redemptions", ["inviter_user_id", "created_at"], unique=False)
    op.create_index("ix_invite_redemptions_invitee", "invite_redemptions", ["invitee_user_id"], unique=True)
    op.create_index("ix_invite_redemptions_code", "invite_redemptions", ["invite_code_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_invite_redemptions_code", table_name="invite_redemptions")
    op.drop_index("ix_invite_redemptions_invitee", table_name="invite_redemptions")
    op.drop_index("ix_invite_redemptions_inviter_created", table_name="invite_redemptions")
    op.drop_table("invite_redemptions")
    op.drop_index("ix_invite_codes_status", table_name="invite_codes")
    op.drop_index("ix_invite_codes_code", table_name="invite_codes")
    op.drop_index("ix_invite_codes_owner_user_id", table_name="invite_codes")
    op.drop_table("invite_codes")
    # PostgreSQL enum values cannot be dropped safely; leave invite wallet transaction values in place.
