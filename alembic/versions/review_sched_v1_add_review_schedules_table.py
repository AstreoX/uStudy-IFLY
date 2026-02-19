"""add review_schedules table

Revision ID: review_sched_v1
Revises: afe91cbe7199
Create Date: 2026-02-19 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'review_sched_v1'
down_revision: Union[str, Sequence[str], None] = 'afe91cbe7199'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('review_schedules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('activity_id', sa.UUID(), nullable=False),
        sa.Column('node_label', sa.String(length=200), nullable=False),
        sa.Column('review_number', sa.Integer(), nullable=False),
        sa.Column('scheduled_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_by_activity_id', sa.UUID(), nullable=True),
        sa.Column('study_depth', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['activity_id'], ['study_activity_logs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['completed_by_activity_id'], ['study_activity_logs.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_review_user_date', 'review_schedules', ['user_id', 'scheduled_date'], unique=False)
    op.create_index('idx_review_user_node', 'review_schedules', ['user_id', 'node_label'], unique=False)
    op.create_index('idx_review_activity', 'review_schedules', ['activity_id'], unique=False)
    op.create_index('idx_review_status_date', 'review_schedules', ['user_id', 'status', 'scheduled_date'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_review_status_date', table_name='review_schedules')
    op.drop_index('idx_review_activity', table_name='review_schedules')
    op.drop_index('idx_review_user_node', table_name='review_schedules')
    op.drop_index('idx_review_user_date', table_name='review_schedules')
    op.drop_table('review_schedules')
