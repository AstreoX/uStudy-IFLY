"""
Previous Conversation Context Loader

加载上一个对话的最后几轮，用于新对话的背景参考。
在学习空间模式下，当用户新开一个对话窗口时，自动加载上一个对话的最后两轮对话，
增强学习连续性。
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Conversation, ConversationKind, Message, MessageRole


async def get_previous_conversation_id(
    db: AsyncSession,
    user_id: UUID,
    space_id: UUID,
    current_conversation_id: UUID,
) -> UUID | None:
    """
    获取上一个对话 ID（按最后用户消息时间排序）

    Args:
        db: 数据库会话
        user_id: 用户 ID
        space_id: 学习空间 ID
        current_conversation_id: 当前对话 ID（排除）

    Returns:
        上一个对话的 ID，或 None（如果没有）

    SQL 逻辑:
    1. 子查询：当前用户/空间下每个对话的最后 user 消息时间（过滤在子查询内部）
    2. 主查询：排除当前对话、按时间倒序取第一个

    Requires index: messages(conversation_id, role, created_at)
    Requires index: conversations(user_id, space_id)
    """
    # 子查询: 当前用户/空间下每个对话的最后 user 消息时间
    # 在子查询内部过滤，避免全表扫描
    last_msg_subq = (
        select(
            Message.conversation_id,
            func.max(Message.created_at).label("last_user_msg_time"),
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Message.role == MessageRole.USER,
            Conversation.user_id == user_id,
            Conversation.space_id == space_id,
            Conversation.id != current_conversation_id,
            Conversation.kind == ConversationKind.LEARNING,
        )
        .group_by(Message.conversation_id)
        .subquery()
    )

    # 主查询：按最后消息时间排序取第一个
    query = (
        select(last_msg_subq.c.conversation_id)
        .order_by(last_msg_subq.c.last_user_msg_time.desc())
        .limit(1)
    )

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def load_last_rounds(
    db: AsyncSession,
    conversation_id: UUID,
    max_rounds: int = 2,
) -> list[Message]:
    """
    加载对话的最后 N 轮（user + assistant 配对）

    Args:
        db: 数据库会话
        conversation_id: 对话 ID
        max_rounds: 最大轮数（默认 2，范围 1-5）

    Returns:
        按时间正序排列的消息列表（最多 2*max_rounds 条）

    注意：一轮 = 1 user + 1 assistant 消息
    """
    # 参数验证：限制在安全范围内
    max_rounds = max(1, min(max_rounds, 5))

    # 倒序加载，只取 USER 和 ASSISTANT 消息，多取一些作为缓冲
    result = await db.execute(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.role.in_([MessageRole.USER, MessageRole.ASSISTANT]),
        )
        .order_by(Message.created_at.desc())
        .limit(max_rounds * 2 + 2)
    )
    messages = list(result.scalars().all())

    # 提取完整轮次
    rounds: list[tuple[Message, Message]] = []
    i = 0

    while i < len(messages) and len(rounds) < max_rounds:
        # 找 assistant 消息（最新的在前）
        if messages[i].role == MessageRole.ASSISTANT:
            assistant_msg = messages[i]
            # 找前一条 user 消息
            if i + 1 < len(messages) and messages[i + 1].role == MessageRole.USER:
                user_msg = messages[i + 1]
                rounds.append((user_msg, assistant_msg))
                i += 2
            else:
                i += 1
        else:
            i += 1

    # 反转为正序，扁平化
    result_messages = []
    for user_msg, assistant_msg in reversed(rounds):
        result_messages.append(user_msg)
        result_messages.append(assistant_msg)

    return result_messages


def format_previous_conversation(
    messages: list[Message],
    max_content_length: int = 1000,
) -> str:
    """
    格式化历史消息为文本

    Args:
        messages: 消息列表
        max_content_length: 单条消息最大长度

    Returns:
        格式化的文本
    """
    if not messages:
        return ""

    # 角色标签映射
    role_labels = {
        MessageRole.USER: "[用户]",
        MessageRole.ASSISTANT: "[AI]",
    }

    lines = []
    for msg in messages:
        role_label = role_labels.get(msg.role, f"[{msg.role.value}]")
        content = msg.content
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."
        lines.append(f"{role_label}: {content}")

    return "\n".join(lines)


async def get_previous_conversation_context(
    db: AsyncSession,
    user_id: UUID,
    space_id: UUID,
    current_conversation_id: UUID,
    max_rounds: int = 2,
    max_content_length: int = 1000,
) -> str | None:
    """
    主入口：获取格式化的上一个对话上下文（限定学习空间）

    Args:
        db: 数据库会话
        user_id: 用户 ID
        space_id: 学习空间 ID
        current_conversation_id: 当前对话 ID
        max_rounds: 加载的最大轮数
        max_content_length: 单条消息最大截断长度

    Returns:
        格式化的上下文字符串，或 None（如果没有上一个对话）
    """
    prev_conv_id = await get_previous_conversation_id(
        db, user_id, space_id, current_conversation_id
    )
    if not prev_conv_id:
        return None

    messages = await load_last_rounds(db, prev_conv_id, max_rounds)
    if not messages:
        return None

    return format_previous_conversation(messages, max_content_length)


async def get_previous_conversation_id_global(
    db: AsyncSession,
    user_id: UUID,
    current_conversation_id: UUID,
) -> UUID | None:
    """
    获取用户最近的对话 ID（跨所有空间 + 快速对话）

    与 get_previous_conversation_id() 的区别：
    - 不过滤 space_id
    - 检索范围：所有学习空间对话 + 快速对话

    Args:
        db: 数据库会话
        user_id: 用户 ID
        current_conversation_id: 当前对话 ID（排除）

    Returns:
        上一个对话的 ID，或 None（如果没有）
    """
    # 子查询: 当前用户所有对话的最后 user 消息时间（不过滤 space_id）
    last_msg_subq = (
        select(
            Message.conversation_id,
            func.max(Message.created_at).label("last_user_msg_time"),
        )
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Message.role == MessageRole.USER,
            Conversation.user_id == user_id,
            Conversation.id != current_conversation_id,
            # 无 space_id 过滤 → 检索所有对话（学习空间 + 快速对话）
        )
        .group_by(Message.conversation_id)
        .subquery()
    )

    # 主查询：按最后消息时间排序取第一个
    query = (
        select(last_msg_subq.c.conversation_id)
        .order_by(last_msg_subq.c.last_user_msg_time.desc())
        .limit(1)
    )

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_previous_conversation_context_global(
    db: AsyncSession,
    user_id: UUID,
    current_conversation_id: UUID,
    max_rounds: int = 2,
    max_content_length: int = 1000,
) -> str | None:
    """
    获取格式化的上一个对话上下文（跨所有对话类型）

    用于快速对话模式的对话连续性，检索用户最近的对话
    （无论是学习空间对话还是快速对话）

    Args:
        db: 数据库会话
        user_id: 用户 ID
        current_conversation_id: 当前对话 ID
        max_rounds: 加载的最大轮数（如不足则加载实际轮数）
        max_content_length: 单条消息最大截断长度

    Returns:
        格式化的上下文字符串，或 None（如果没有上一个对话）
    """
    prev_conv_id = await get_previous_conversation_id_global(
        db, user_id, current_conversation_id
    )
    if not prev_conv_id:
        return None

    # 复用现有的 load_last_rounds（会返回实际存在的轮数）
    messages = await load_last_rounds(db, prev_conv_id, max_rounds)
    if not messages:
        return None

    return format_previous_conversation(messages, max_content_length)
