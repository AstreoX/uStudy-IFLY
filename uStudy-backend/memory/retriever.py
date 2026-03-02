"""记忆检索器 - 基于用户消息检索相关记忆，用于 prompt 注入"""

import asyncio
import logging
import time
from uuid import UUID

from sqlalchemy import or_, select

from config import get_settings
from db.database import get_scoped_session
from db.models import MemoryType, Space
from memory.schemas import MemorySearchResult
from memory.service import MemoryService

logger = logging.getLogger(__name__)


class MemoryRetriever:
    """记忆检索器 - 为 prompt 注入提供相关记忆"""

    def __init__(self, user_id: UUID, space_id: UUID | None = None) -> None:
        """
        初始化记忆检索器

        Args:
            user_id: 用户 ID
            space_id: 学习空间 ID（可选，用于检索空间记忆）
        """
        self.user_id = user_id
        self.space_id = space_id
        self.memory_service = MemoryService()
        self.settings = get_settings()

    async def get_relevant_memories(
        self,
        user_message: str,
        max_long_term: int | None = None,
        max_space: int | None = None,
    ) -> dict[str, list[MemorySearchResult]]:
        """
        检索与当前消息相关的记忆

        Args:
            user_message: 用户消息内容
            max_long_term: 最大长期记忆数量
            max_space: 最大空间记忆数量

        Returns:
            {
                "long_term": [MemorySearchResult, ...],
                "space": [MemorySearchResult, ...]
            }
        """
        # 使用配置默认值
        if max_long_term is None:
            max_long_term = getattr(
                self.settings, "memory_search_top_k_long_term", 5
            )
        if max_space is None:
            max_space = getattr(self.settings, "memory_search_top_k_space", 5)

        score_threshold = getattr(
            self.settings, "memory_search_score_threshold", 0.3
        )

        # 预计算一次 embedding，两次搜索共用（省去重复 API 调用）
        embed_start = time.monotonic()
        query_embedding = await self.memory_service.embedding_client.embed_query(
            user_message
        )
        embed_ms = (time.monotonic() - embed_start) * 1000
        logger.info(f"[Perf] Memory embedding computed once: {embed_ms:.0f}ms")

        # 并行搜索长期记忆和空间记忆（传入预计算向量）
        long_term_task = self.memory_service.search_memories(
            user_id=self.user_id,
            query=user_message,
            memory_type=MemoryType.LONG_TERM,
            top_k=max_long_term,
            score_threshold=score_threshold,
            query_embedding=query_embedding,
        )

        if self.space_id:
            # 获取可检索的空间列表（当前空间 + 开启共享的其他空间）
            searchable_space_ids = await self._get_searchable_space_ids()

            space_task = self.memory_service.search_memories(
                user_id=self.user_id,
                query=user_message,
                memory_type=MemoryType.SPACE,
                space_ids=searchable_space_ids,
                top_k=max_space,
                score_threshold=score_threshold,
                query_embedding=query_embedding,
            )
        else:
            # 没有空间 ID，返回空列表

            async def empty_list() -> list[MemorySearchResult]:
                return []

            space_task = empty_list()

        long_term, space = await asyncio.gather(long_term_task, space_task)

        logger.debug(
            f"Retrieved memories for user {self.user_id}: "
            f"{len(long_term)} long-term, {len(space)} space"
        )

        return {
            "long_term": long_term,
            "space": space,
        }

    async def _get_searchable_space_ids(self) -> list[UUID]:
        """
        获取可检索的空间 ID 列表：
        - 当前空间（始终包含）
        - 用户其他开启了 memory_sharing_enabled 的空间

        Returns:
            可检索的空间 ID 列表
        """
        async with get_scoped_session() as db:
            result = await db.execute(
                select(Space.id).where(
                    Space.user_id == self.user_id,
                    or_(
                        Space.id == self.space_id,
                        Space.memory_sharing_enabled == True,  # noqa: E712
                    ),
                )
            )
            space_ids = list(result.scalars().all())

            if len(space_ids) > 1:
                logger.debug(
                    f"Memory sharing: searching {len(space_ids)} spaces "
                    f"(current + {len(space_ids) - 1} shared)"
                )

            return space_ids


def format_memories_for_prompt(
    memories: dict[str, list[MemorySearchResult]],
    current_space_id: UUID | None = None,
) -> str:
    """
    将检索到的记忆格式化为 prompt 注入格式

    Args:
        memories: {"long_term": [...], "space": [...]}
        current_space_id: 当前空间 ID（用于区分本空间/共享记忆）

    Returns:
        格式化的字符串，用于注入系统提示词
    """
    sections = []

    # 长期记忆
    long_term = memories.get("long_term", [])
    if long_term:
        lt_lines = [f"- {m.content}" for m in long_term]
        sections.append("## 关于用户的记忆\n" + "\n".join(lt_lines))

    # 空间记忆（区分本空间/共享）
    space = memories.get("space", [])
    if space:
        local_lines = []
        shared_lines = []

        for m in space:
            if current_space_id and m.space_id != current_space_id:
                shared_lines.append(f"- {m.content}")
            else:
                local_lines.append(f"- {m.content}")

        if local_lines:
            sections.append(
                "## 关于当前学习空间的记忆\n" + "\n".join(local_lines)
            )
        if shared_lines:
            sections.append(
                "## 来自其他学习空间的共享记忆\n" + "\n".join(shared_lines)
            )

    if not sections:
        return ""

    return "# 相关记忆\n\n" + "\n\n".join(sections)
