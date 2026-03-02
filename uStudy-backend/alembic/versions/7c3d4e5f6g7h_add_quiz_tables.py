"""add_quiz_tables

Revision ID: 7c3d4e5f6g7h
Revises: 6b2c3d4e5f6g
Create Date: 2026-02-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7c3d4e5f6g7h'
down_revision: Union[str, Sequence[str], None] = '6b2c3d4e5f6g'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create quizzes and questions tables with enum types."""
    # 创建枚举类型（使用小写值，与 Python Enum 值匹配）
    questiontype = postgresql.ENUM(
        'single_choice', 'multiple_choice', 'true_false', 'short_answer',
        name='questiontype',
        create_type=False
    )
    difficultylevel = postgresql.ENUM(
        'easy', 'medium', 'hard',
        name='difficultylevel',
        create_type=False
    )

    # 先创建枚举类型（如果不存在）
    op.execute("CREATE TYPE questiontype AS ENUM ('single_choice', 'multiple_choice', 'true_false', 'short_answer')")
    op.execute("CREATE TYPE difficultylevel AS ENUM ('easy', 'medium', 'hard')")

    # 创建 quizzes 表
    op.create_table(
        'quizzes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('space_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('topic', sa.String(500), nullable=False),
        sa.Column('difficulty', difficultylevel, nullable=False, server_default='medium'),
        sa.Column('total_questions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['space_id'], ['spaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_task_id'], ['agent_tasks.id'], ondelete='SET NULL'),
    )

    # 创建 quizzes 索引
    op.create_index('ix_quizzes_space_id', 'quizzes', ['space_id'])
    op.create_index('ix_quizzes_agent_task_id', 'quizzes', ['agent_task_id'])

    # 创建 questions 表
    op.create_table(
        'questions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quiz_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('question_type', questiontype, nullable=False),
        sa.Column('question_stem', sa.Text(), nullable=False),
        sa.Column('options', postgresql.JSON(), nullable=True),
        sa.Column('correct_answer', postgresql.JSON(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['quiz_id'], ['quizzes.id'], ondelete='CASCADE'),
    )

    # 创建 questions 索引
    op.create_index('ix_questions_quiz_id', 'questions', ['quiz_id'])


def downgrade() -> None:
    """Drop questions and quizzes tables with enum types."""
    # 删除 questions 表
    op.drop_index('ix_questions_quiz_id', table_name='questions')
    op.drop_table('questions')

    # 删除 quizzes 表
    op.drop_index('ix_quizzes_agent_task_id', table_name='quizzes')
    op.drop_index('ix_quizzes_space_id', table_name='quizzes')
    op.drop_table('quizzes')

    # 删除枚举类型
    op.execute("DROP TYPE difficultylevel")
    op.execute("DROP TYPE questiontype")
