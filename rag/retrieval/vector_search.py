"""pgvector 向量搜索"""

import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from rag.embedding import EmbeddingClient

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class SearchResult:
    """搜索结果"""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    score: float
    metadata: dict
    document_title: str
    document_filename: Optional[str]


class VectorSearchService:
    """向量搜索服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.embedding_client = EmbeddingClient()

    async def search(
        self,
        query: str,
        space_id: uuid.UUID,
        top_k: int = 10,
        score_threshold: float = 0.0,
    ) -> list[SearchResult]:
        """
        在指定空间中搜索相关文档切片

        Args:
            query: 搜索查询
            space_id: 学习空间 ID
            top_k: 返回结果数量
            score_threshold: 最低相似度阈值 (0-1)

        Returns:
            搜索结果列表
        """
        # 生成查询向量
        logger.info("生成查询向量: %s", query[:50])
        query_embedding = await self.embedding_client.embed_query(query)

        # 将 embedding 转换为字符串格式供 pgvector 使用
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # 使用 pgvector 进行相似度搜索
        # 使用 cosine 距离，1 - distance = similarity
        # 注意：使用 CAST() 替代 :: 类型转换，避免 SQLAlchemy text() 解析冲突
        sql = text(
            """
            SELECT
                dc.id,
                dc.document_id,
                dc.content,
                dc.chunk_metadata,
                1 - (dc.embedding <=> CAST(:query_embedding AS vector)) as score,
                sd.title as document_title,
                sd.original_filename as document_filename
            FROM document_chunks dc
            JOIN space_documents sd ON dc.document_id = sd.id
            WHERE dc.space_id = :space_id
              AND dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :top_k
            """
        )

        result = await self.db.execute(
            sql,
            {
                "query_embedding": embedding_str,
                "space_id": space_id,
                "top_k": top_k,
            },
        )

        rows = result.fetchall()

        # 过滤低于阈值的结果
        results = []
        for row in rows:
            if row.score >= score_threshold:
                results.append(
                    SearchResult(
                        chunk_id=row.id,
                        document_id=row.document_id,
                        content=row.content,
                        score=row.score,
                        metadata=row.chunk_metadata or {},
                        document_title=row.document_title,
                        document_filename=row.document_filename,
                    )
                )

        logger.info("搜索完成，返回 %d 条结果", len(results))
        return results

    async def search_by_embedding(
        self,
        embedding: list[float],
        space_id: uuid.UUID,
        top_k: int = 10,
        score_threshold: float = 0.0,
    ) -> list[SearchResult]:
        """
        使用已生成的向量进行搜索

        Args:
            embedding: 查询向量
            space_id: 学习空间 ID
            top_k: 返回结果数量
            score_threshold: 最低相似度阈值

        Returns:
            搜索结果列表
        """
        # 将 embedding 转换为字符串格式供 pgvector 使用
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        # 注意：使用 CAST() 替代 :: 类型转换，避免 SQLAlchemy text() 解析冲突
        sql = text(
            """
            SELECT
                dc.id,
                dc.document_id,
                dc.content,
                dc.chunk_metadata,
                1 - (dc.embedding <=> CAST(:query_embedding AS vector)) as score,
                sd.title as document_title,
                sd.original_filename as document_filename
            FROM document_chunks dc
            JOIN space_documents sd ON dc.document_id = sd.id
            WHERE dc.space_id = :space_id
              AND dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :top_k
            """
        )

        result = await self.db.execute(
            sql,
            {
                "query_embedding": embedding_str,
                "space_id": space_id,
                "top_k": top_k,
            },
        )

        rows = result.fetchall()

        results = []
        for row in rows:
            if row.score >= score_threshold:
                results.append(
                    SearchResult(
                        chunk_id=row.id,
                        document_id=row.document_id,
                        content=row.content,
                        score=row.score,
                        metadata=row.chunk_metadata or {},
                        document_title=row.document_title,
                        document_filename=row.document_filename,
                    )
                )

        return results

    async def search_multi_space(
        self,
        query: str,
        space_ids: list[uuid.UUID],
        top_k: int = 10,
        score_threshold: float = 0.0,
    ) -> list[SearchResult]:
        """
        在多个空间中搜索

        Args:
            query: 搜索查询
            space_ids: 学习空间 ID 列表
            top_k: 返回结果数量
            score_threshold: 最低相似度阈值

        Returns:
            搜索结果列表（按相似度排序）
        """
        if not space_ids:
            return []

        query_embedding = await self.embedding_client.embed_query(query)

        # 将 embedding 转换为字符串格式供 pgvector 使用
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # 构建 IN 查询
        # 注意：使用 CAST() 替代 :: 类型转换，避免 SQLAlchemy text() 解析冲突
        sql = text(
            """
            SELECT
                dc.id,
                dc.document_id,
                dc.content,
                dc.chunk_metadata,
                dc.space_id,
                1 - (dc.embedding <=> CAST(:query_embedding AS vector)) as score,
                sd.title as document_title,
                sd.original_filename as document_filename
            FROM document_chunks dc
            JOIN space_documents sd ON dc.document_id = sd.id
            WHERE dc.space_id = ANY(:space_ids)
              AND dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :top_k
            """
        )

        result = await self.db.execute(
            sql,
            {
                "query_embedding": embedding_str,
                "space_ids": space_ids,
                "top_k": top_k,
            },
        )

        rows = result.fetchall()

        results = []
        for row in rows:
            if row.score >= score_threshold:
                results.append(
                    SearchResult(
                        chunk_id=row.id,
                        document_id=row.document_id,
                        content=row.content,
                        score=row.score,
                        metadata=row.chunk_metadata or {},
                        document_title=row.document_title,
                        document_filename=row.document_filename,
                    )
                )

        return results
