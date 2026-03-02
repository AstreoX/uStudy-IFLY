"""Long-Term Memory Tool Executor"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chat.tools.base import ToolResult
from db.database import get_scoped_session
from db.models import LongTermMemory

logger = logging.getLogger(__name__)

# 条目数上限
MAX_ENTRIES = 100
# 单条内容最大长度
MAX_CONTENT_LENGTH = 500


class MemoryToolExecutor:
    """长期记忆工具执行器"""

    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """
        执行记忆工具。每次调用创建独立的短生命周期 DB session。

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            ToolResult 执行结果
        """
        method_map = {
            "write_to_long_term_memory": self._write_memory,
            "delete_from_long_term_memory": self._delete_memory,
        }

        handler = method_map.get(tool_name)
        if not handler:
            return ToolResult(
                success=False,
                data=None,
                message=f"未知的记忆工具: {tool_name}",
            )

        try:
            async with get_scoped_session() as db:
                return await handler(arguments, db)
        except Exception as e:
            logger.error(f"Memory tool error [{tool_name}]: {e}", exc_info=True)
            return ToolResult(
                success=False,
                data=None,
                message=f"工具执行失败: {str(e)}",
            )

    async def _get_or_create_memory(self, db: AsyncSession) -> LongTermMemory:
        """获取或创建用户的长期记忆记录"""
        result = await db.execute(
            select(LongTermMemory).where(LongTermMemory.user_id == self.user_id)
        )
        memory = result.scalar_one_or_none()

        if not memory:
            memory = LongTermMemory(
                user_id=self.user_id,
                entries=[],
                next_entry_id=1,
            )
            db.add(memory)
            await db.flush()

        return memory

    async def _write_memory(self, args: dict[str, Any], db: AsyncSession) -> ToolResult:
        """写入长期记忆"""
        content = args.get("memory_content", "").strip()

        if not content:
            return ToolResult(
                success=False,
                data=None,
                message="记忆内容不能为空",
            )

        if len(content) > MAX_CONTENT_LENGTH:
            content = content[:MAX_CONTENT_LENGTH]

        memory = await self._get_or_create_memory(db)

        # 检查条目数上限
        if len(memory.entries) >= MAX_ENTRIES:
            return ToolResult(
                success=False,
                data={"current_count": len(memory.entries)},
                message=f"长期记忆已达上限（{MAX_ENTRIES}条），请删除一些旧记忆后再添加",
            )

        # 创建新条目
        new_entry = {
            "id": memory.next_entry_id,
            "content": content,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }

        # 更新记忆（创建新列表以触发 JSONB 更新）
        updated_entries = list(memory.entries)
        updated_entries.append(new_entry)
        memory.entries = updated_entries
        memory.next_entry_id = memory.next_entry_id + 1

        await db.commit()

        logger.info(f"Written memory #{new_entry['id']} for user {self.user_id}")

        return ToolResult(
            success=True,
            data={"entry_id": new_entry["id"], "content": content},
            message=f"已记住（#{new_entry['id']}）：{content[:50]}{'...' if len(content) > 50 else ''}",
        )

    async def _delete_memory(self, args: dict[str, Any], db: AsyncSession) -> ToolResult:
        """删除长期记忆"""
        entry_id = args.get("entry_id")
        clear_all = args.get("clear_all", False)

        memory = await self._get_or_create_memory(db)

        if clear_all:
            # 清空所有记忆
            deleted_count = len(memory.entries)
            memory.entries = []
            memory.next_entry_id = 1
            await db.commit()

            logger.info(f"Cleared all memories for user {self.user_id}")

            return ToolResult(
                success=True,
                data={"deleted_count": deleted_count},
                message=f"已清空所有长期记忆（共{deleted_count}条）",
            )

        if entry_id is None:
            return ToolResult(
                success=False,
                data=None,
                message="请提供要删除的条目序号(entry_id)或设置clear_all=true",
            )

        # 按序号删除
        original_count = len(memory.entries)
        updated_entries = [e for e in memory.entries if e.get("id") != entry_id]

        if len(updated_entries) == original_count:
            return ToolResult(
                success=False,
                data=None,
                message=f"未找到序号为 {entry_id} 的记忆条目",
            )

        memory.entries = updated_entries
        await db.commit()

        logger.info(f"Deleted memory #{entry_id} for user {self.user_id}")

        return ToolResult(
            success=True,
            data={"deleted_entry_id": entry_id},
            message=f"已删除记忆条目 #{entry_id}",
        )


def format_memory_for_prompt(entries: list[dict[str, Any]]) -> str:
    """
    将记忆条目格式化为提示词注入格式

    Args:
        entries: 记忆条目列表

    Returns:
        格式化的字符串，用于注入系统提示词
    """
    if not entries:
        return "暂无长期记忆"

    lines = []
    for entry in entries:
        entry_id = entry.get("id", "?")
        created_at = entry.get("created_at", "未知")
        content = entry.get("content", "")
        lines.append(f"#{entry_id} [{created_at}] {content}")

    return "\n".join(lines)
