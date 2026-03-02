"""add study_activity_logs table

Revision ID: afe91cbe7199
Revises: daily_study_v1
Create Date: 2026-02-19 15:27:59.439155

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'afe91cbe7199'
down_revision: Union[str, Sequence[str], None] = 'daily_study_v1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('study_activity_logs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('conversation_id', sa.UUID(), nullable=True),
    sa.Column('space_id', sa.UUID(), nullable=True),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('summary', sa.String(length=1000), nullable=False),
    sa.Column('activity_type', sa.String(length=50), nullable=False),
    sa.Column('subject_name', sa.String(length=200), nullable=True),
    sa.Column('related_node_labels', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('message_count', sa.Integer(), nullable=False),
    sa.Column('study_depth', sa.String(length=50), nullable=True),
    sa.Column('source', sa.String(length=50), nullable=False),
    sa.Column('activity_date', sa.Date(), nullable=False),
    sa.Column('activity_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['space_id'], ['spaces.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_activity_conversation', 'study_activity_logs', ['conversation_id'], unique=False)
    op.create_index('idx_activity_user_date', 'study_activity_logs', ['user_id', 'activity_date'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_activity_user_date', table_name='study_activity_logs')
    op.drop_index('idx_activity_conversation', table_name='study_activity_logs')
    op.drop_table('study_activity_logs')
