"""向量记忆服务 - 核心记忆存储和检索功能"""

import logging
from uuid import UUID

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_scoped_session
from db.models import MemoryType, VectorMemory
from memory.schemas import MemorySearchResult
from rag.embedding import EmbeddingClient

logger = logging.getLogger(__name__)


class MemoryService:
    """向量记忆服务"""

    def __init__(self) -> None:
        self.embedding_client = EmbeddingClient()

    async def add_memory(
        self,
        user_id: UUID,
        content: str,
        memory_type: MemoryType,
        space_id: UUID | None = None,
        extra_data: dict | None = None,
    ) -> VectorMemory:
        """
        添加记忆（自动生成 embedding）

        Args:
            user_id: 用户 ID
            content: 记忆内容
            memory_type: 记忆类型 (LONG_TERM | SPACE)
            space_id: 学习空间 ID（空间记忆必填）
            extra_data: 可选元数据

        Returns:
            新创建的 VectorMemory 对象
        """
        # 验证参数
        if memory_type == MemoryType.SPACE and space_id is None:
            raise ValueError("Space memory requires space_id")

        # 生成 embedding
        embedding = await self.embedding_client.embed(content)

        async with get_scoped_session() as db:
            memory = VectorMemory(
                user_id=user_id,
                space_id=space_id,
                memory_type=memory_type,
                content=content,
                embedding=embedding,
                extra_data=extra_data,
            )
            db.add(memory)
            await db.commit()
            await db.refresh(memory)

            logger.info(
                f"Added {memory_type.value} memory for user {user_id}"
                + (f" in space {space_id}" if space_id else "")
            )
            return memory

    async def search_memories(
        self,
        user_id: UUID,
        query: str,
        memory_type: MemoryType | None = None,
        space_id: UUID | None = None,
        space_ids: list[UUID] | None = None,
        top_k: int = 5,
        score_threshold: float = 0.3,
    ) -> list[MemorySearchResult]:
        """
        语义搜索记忆

        Args:
            user_id: 用户 ID
            query: 搜索查询
            memory_type: 限定记忆类型（可选）
            space_id: 限定空间（可选，仅对 SPACE 类型有效）
            space_ids: 限定多个空间（可选，用于记忆共享场景）
            top_k: 返回结果数量
            score_threshold: 最低相似度阈值 (0-1)

        Returns:
            按相似度排序的记忆搜索结果
        """
        # 生成查询向量
        query_embedding = await self.embedding_client.embed_query(query)
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        async with get_scoped_session() as db:
            # 构建动态 WHERE 条件
            conditions = ["user_id = :user_id"]
            params: dict = {
                "user_id": user_id,
                "query_embedding": embedding_str,
                "top_k": top_k,
            }

            if memory_type:
                conditions.append("memory_type = :memory_type")
                params["memory_type"] = memory_type.value

            # 支持多空间检索（记忆共享场景）
            if space_ids:
                conditions.append("space_id = ANY(:space_ids)")
                params["space_ids"] = [str(sid) for sid in space_ids]
            elif space_id:
                conditions.append("space_id = :space_id")
                params["space_id"] = space_id

            where_clause = " AND ".join(conditions)

            sql = text(f"""
                SELECT
                    id, content, memory_type, space_id, created_at, extra_data,
                    1 - (embedding <=> CAST(:query_embedding AS vector)) as score
                FROM vector_memories
                WHERE {where_clause}
                ORDER BY embedding <=> CAST(:query_embedding AS vector)
                LIMIT :top_k
            """)

            result = await db.execute(sql, params)
            rows = result.fetchall()

            results = []
            for row in rows:
                if row.score >= score_threshold:
                    results.append(
                        MemorySearchResult(
                            id=row.id,
                            content=row.content,
                            score=row.score,
                            memory_type=MemoryType(row.memory_type),
                            created_at=row.created_at,
                            space_id=row.space_id,
                            extra_data=row.extra_data,
                        )
                    )

            logger.debug(
                f"Searched memories for user {user_id}, found {len(results)} results"
            )
            return results

    async def delete_memory(
        self,
        memory_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        删除单条记忆

        Args:
            memory_id: 记忆 ID
            user_id: 用户 ID（用于权限验证）

        Returns:
            是否成功删除
        """
        async with get_scoped_session() as db:
            result = await db.execute(
                delete(VectorMemory).where(
                    VectorMemory.id == memory_id,
                    VectorMemory.user_id == user_id,
                )
            )
            await db.commit()

            deleted = result.rowcount > 0
            if deleted:
                logger.info(f"Deleted memory {memory_id} for user {user_id}")
            return deleted

    async def delete_all_memories(
        self,
        user_id: UUID,
        memory_type: MemoryType | None = None,
        space_id: UUID | None = None,
    ) -> int:
        """
        批量删除记忆

        Args:
            user_id: 用户 ID
            memory_type: 限定记忆类型（可选）
            space_id: 限定空间（可选）

        Returns:
            删除的记忆数量
        """
        async with get_scoped_session() as db:
            # 构建删除条件
            conditions = [VectorMemory.user_id == user_id]

            if memory_type:
                conditions.append(VectorMemory.memory_type == memory_type)

            if space_id:
                conditions.append(VectorMemory.space_id == space_id)

            result = await db.execute(delete(VectorMemory).where(*conditions))
            await db.commit()

            count = result.rowcount
            logger.info(
                f"Deleted {count} memories for user {user_id}"
                + (f" (type={memory_type.value})" if memory_type else "")
                + (f" (space={space_id})" if space_id else "")
            )
            return count

    async def get_memory_by_id(
        self,
        memory_id: UUID,
        user_id: UUID,
    ) -> VectorMemory | None:
        """
        通过 ID 获取记忆

        Args:
            memory_id: 记忆 ID
            user_id: 用户 ID（用于权限验证）

        Returns:
            VectorMemory 对象或 None
        """
        async with get_scoped_session() as db:
            sql = text("""
                SELECT id, user_id, space_id, memory_type, content, extra_data, created_at
                FROM vector_memories
                WHERE id = :memory_id AND user_id = :user_id
            """)
            result = await db.execute(
                sql, {"memory_id": memory_id, "user_id": user_id}
            )
            row = result.fetchone()

            if row:
                return VectorMemory(
                    id=row.id,
                    user_id=row.user_id,
                    space_id=row.space_id,
                    memory_type=MemoryType(row.memory_type),
                    content=row.content,
                    extra_data=row.extra_data,
                    created_at=row.created_at,
                    embedding=[],  # 不返回 embedding
                )
            return None
