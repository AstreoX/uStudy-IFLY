"""Vector Memory Tool Executor - 向量记忆工具执行器"""

import logging
from typing import Any
from uuid import UUID

from chat.tools.base import ToolResult
from db.models import MemoryType
from memory.service import MemoryService

logger = logging.getLogger(__name__)


class VectorMemoryExecutor:
    """向量记忆工具执行器"""

    def __init__(self, user_id: UUID, space_id: UUID | None = None) -> None:
        """
        初始化执行器

        Args:
            user_id: 用户 ID
            space_id: 学习空间 ID（可选，用于空间记忆）
        """
        self.user_id = user_id
        self.space_id = space_id
        self.memory_service = MemoryService()

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """
        执行记忆工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            ToolResult 执行结果
        """
        method_map = {
            "remember": self._remember,
            "remember_space": self._remember_space,
            "forget": self._forget,
            "search_memories": self._search,
        }

        handler = method_map.get(tool_name)
        if not handler:
            return ToolResult(
                success=False,
                data=None,
                message=f"未知的记忆工具: {tool_name}",
            )

        try:
            return await handler(arguments)
        except Exception as e:
            logger.error(f"Memory tool error [{tool_name}]: {e}", exc_info=True)
            return ToolResult(
                success=False,
                data=None,
                message=f"工具执行失败: {str(e)}",
            )

    async def _remember(self, args: dict[str, Any]) -> ToolResult:
        """写入长期记忆"""
        content = args.get("content", "").strip()

        if not content:
            return ToolResult(
                success=False,
                data=None,
                message="记忆内容不能为空",
            )

        memory = await self.memory_service.add_memory(
            user_id=self.user_id,
            content=content,
            memory_type=MemoryType.LONG_TERM,
            extra_data={"source": "tool_call"},
        )

        logger.info(f"Saved long-term memory {memory.id} for user {self.user_id}")

        return ToolResult(
            success=True,
            data={"memory_id": str(memory.id)},
            message=f"已记住：{content[:50]}{'...' if len(content) > 50 else ''}",
        )

    async def _remember_space(self, args: dict[str, Any]) -> ToolResult:
        """写入空间记忆"""
        if not self.space_id:
            return ToolResult(
                success=False,
                data=None,
                message="当前不在学习空间内，无法保存空间记忆",
            )

        content = args.get("content", "").strip()

        if not content:
            return ToolResult(
                success=False,
                data=None,
                message="记忆内容不能为空",
            )

        memory = await self.memory_service.add_memory(
            user_id=self.user_id,
            content=content,
            memory_type=MemoryType.SPACE,
            space_id=self.space_id,
            extra_data={"source": "tool_call"},
        )

        logger.info(
            f"Saved space memory {memory.id} for user {self.user_id} "
            f"in space {self.space_id}"
        )

        return ToolResult(
            success=True,
            data={"memory_id": str(memory.id)},
            message=f"已为当前学习空间记住：{content[:50]}{'...' if len(content) > 50 else ''}",
        )

    async def _forget(self, args: dict[str, Any]) -> ToolResult:
        """删除记忆"""
        memory_id_str = args.get("memory_id")
        clear_all_long_term = args.get("clear_all_long_term", False)
        clear_all_space = args.get("clear_all_space", False)

        # 清空所有长期记忆
        if clear_all_long_term:
            count = await self.memory_service.delete_all_memories(
                user_id=self.user_id,
                memory_type=MemoryType.LONG_TERM,
            )
            logger.info(f"Cleared {count} long-term memories for user {self.user_id}")
            return ToolResult(
                success=True,
                data={"deleted_count": count},
                message=f"已清空所有长期记忆（共 {count} 条）",
            )

        # 清空当前空间记忆
        if clear_all_space:
            if not self.space_id:
                return ToolResult(
                    success=False,
                    data=None,
                    message="当前不在学习空间内",
                )
            count = await self.memory_service.delete_all_memories(
                user_id=self.user_id,
                memory_type=MemoryType.SPACE,
                space_id=self.space_id,
            )
            logger.info(
                f"Cleared {count} space memories for user {self.user_id} "
                f"in space {self.space_id}"
            )
            return ToolResult(
                success=True,
                data={"deleted_count": count},
                message=f"已清空当前学习空间的所有记忆（共 {count} 条）",
            )

        # 删除单条记忆
        if memory_id_str:
            try:
                memory_id = UUID(memory_id_str)
            except ValueError:
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"无效的记忆 ID 格式: {memory_id_str}",
                )

            deleted = await self.memory_service.delete_memory(
                memory_id=memory_id,
                user_id=self.user_id,
            )

            if deleted:
                logger.info(f"Deleted memory {memory_id} for user {self.user_id}")
                return ToolResult(
                    success=True,
                    data={"deleted_memory_id": str(memory_id)},
                    message=f"已删除记忆",
                )
            else:
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"未找到指定的记忆或无权删除",
                )

        return ToolResult(
            success=False,
            data=None,
            message="请提供 memory_id 或设置 clear_all_long_term/clear_all_space",
        )

    async def _search(self, args: dict[str, Any]) -> ToolResult:
        """搜索记忆"""
        query = args.get("query", "").strip()
        scope = args.get("scope", "all")
        limit = min(max(args.get("limit", 5), 1), 20)

        if not query:
            return ToolResult(
                success=False,
                data=None,
                message="搜索查询不能为空",
            )

        results = []

        # 根据范围搜索
        if scope in ("long_term", "all"):
            long_term_results = await self.memory_service.search_memories(
                user_id=self.user_id,
                query=query,
                memory_type=MemoryType.LONG_TERM,
                top_k=limit,
            )
            results.extend(long_term_results)

        if scope in ("space", "all") and self.space_id:
            space_results = await self.memory_service.search_memories(
                user_id=self.user_id,
                query=query,
                memory_type=MemoryType.SPACE,
                space_id=self.space_id,
                top_k=limit,
            )
            results.extend(space_results)

        # 按分数排序并限制数量
        results.sort(key=lambda x: x.score, reverse=True)
        results = results[:limit]

        # 格式化结果
        formatted_results = [
            {
                "id": str(r.id),
                "content": r.content,
                "type": r.memory_type.value,
                "score": round(r.score, 3),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in results
        ]

        logger.debug(
            f"Searched memories for user {self.user_id}: "
            f"query='{query[:30]}...', found {len(results)} results"
        )

        if results:
            summary_lines = [
                f"- [{r['type']}] {r['content'][:50]}... (ID: {r['id'][:8]}..., 相关度: {r['score']})"
                for r in formatted_results[:5]
            ]
            summary = "\n".join(summary_lines)
            return ToolResult(
                success=True,
                data={"results": formatted_results, "total": len(results)},
                message=f"找到 {len(results)} 条相关记忆：\n{summary}",
            )
        else:
            return ToolResult(
                success=True,
                data={"results": [], "total": 0},
                message="未找到相关记忆",
            )
