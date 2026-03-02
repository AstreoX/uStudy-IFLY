"""add_agent_tasks_table

Revision ID: 5a1b2c3d4e5f
Revises: 4f6c30237549
Create Date: 2026-01-31 19:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5a1b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = '4f6c30237549'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create agent_tasks table with enum types."""
    # 创建枚举类型（使用大写值，与 Python Enum 名称匹配）
    agenttaskstatus = postgresql.ENUM(
        'PENDING', 'RUNNING', 'DONE', 'FAILED',
        name='agenttaskstatus',
        create_type=False
    )
    agenttasktype = postgresql.ENUM(
        'GENERATE_KNOWLEDGE_GRAPH', 'GENERATE_QUIZ',
        name='agenttasktype',
        create_type=False
    )

    # 先创建枚举类型（如果不存在）
    op.execute("CREATE TYPE agenttaskstatus AS ENUM ('PENDING', 'RUNNING', 'DONE', 'FAILED')")
    op.execute("CREATE TYPE agenttasktype AS ENUM ('GENERATE_KNOWLEDGE_GRAPH', 'GENERATE_QUIZ')")

    # 创建 agent_tasks 表
    op.create_table(
        'agent_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('space_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('task_type', agenttasktype, nullable=False),
        sa.Column('status', agenttaskstatus, nullable=False, server_default='PENDING'),
        sa.Column('input_data', postgresql.JSON(), nullable=False),
        sa.Column('output_data', postgresql.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['space_id'], ['spaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
    )

    # 创建索引
    op.create_index('ix_agent_tasks_user_id', 'agent_tasks', ['user_id'])
    op.create_index('ix_agent_tasks_space_id', 'agent_tasks', ['space_id'])
    op.create_index('ix_agent_tasks_status', 'agent_tasks', ['status'])


def downgrade() -> None:
    """Drop agent_tasks table and enum types."""
    # 删除索引
    op.drop_index('ix_agent_tasks_status', table_name='agent_tasks')
    op.drop_index('ix_agent_tasks_space_id', table_name='agent_tasks')
    op.drop_index('ix_agent_tasks_user_id', table_name='agent_tasks')

    # 删除表
    op.drop_table('agent_tasks')

    # 删除枚举类型
    op.execute("DROP TYPE agenttasktype")
    op.execute("DROP TYPE agenttaskstatus")
