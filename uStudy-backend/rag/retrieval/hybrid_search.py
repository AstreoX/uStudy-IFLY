"""混合搜索：向量语义搜索 + PostgreSQL 全文检索 + RRF 融合"""

import asyncio
import logging
import math
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from rag.embedding import EmbeddingClient
from rag.retrieval.text_segmentation import build_tsquery
from rag.retrieval.vector_search import SearchResult

logger = logging.getLogger(__name__)
settings = get_settings()


class HybridSearchService:
    """混合搜索服务：向量 + 全文检索 + RRF 融合"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.embedding_client = EmbeddingClient()

    async def search(
        self,
        query: str,
        space_id: uuid.UUID,
        top_k: int = 10,
        score_threshold: float = 0.0,
        vector_weight: float | None = None,
        text_weight: float | None = None,
        rrf_k: int | None = None,
        fetch_k: int | None = None,
    ) -> list[SearchResult]:
        """
        混合搜索：并发执行向量搜索与全文检索，用 RRF 融合排序。

        Args:
            query: 搜索查询
            space_id: 学习空间 ID
            top_k: 最终返回结果数量
            score_threshold: 最低相似度阈值（应用于向量搜索结果）
            vector_weight: RRF 向量权重（默认用配置值）
            text_weight: RRF 全文权重（默认用配置值）
            rrf_k: RRF 常数（默认用配置值）
            fetch_k: 每路搜索候选数量（默认用配置值）

        Returns:
            按 RRF 分数排序的搜索结果列表
        """
        vector_weight = vector_weight or settings.hybrid_vector_weight
        text_weight = text_weight or settings.hybrid_text_weight
        rrf_k = rrf_k or settings.hybrid_rrf_k
        fetch_k = fetch_k or settings.hybrid_fetch_k

        # 1. 生成查询嵌入
        logger.info("混合搜索: 生成查询向量: %s", query[:50])
        query_embedding = await self.embedding_client.embed_query(query)
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # 2. 构建全文检索 tsquery
        tsquery_str = build_tsquery(query)

        # 3. 并发执行两路搜索
        vector_task = self._vector_search(embedding_str, space_id, fetch_k)
        fts_task = self._fulltext_search(tsquery_str, space_id, fetch_k)

        vector_results, fts_results = await asyncio.gather(
            vector_task, fts_task, return_exceptions=True
        )

        # 处理异常情况
        if isinstance(vector_results, Exception):
            logger.warning("向量搜索失败: %s", vector_results)
            vector_results = []
        if isinstance(fts_results, Exception):
            logger.warning("全文检索失败: %s", fts_results)
            fts_results = []

        logger.info(
            "混合搜索: 向量结果 %d 条, 全文结果 %d 条",
            len(vector_results),
            len(fts_results),
        )

        # 4. RRF 融合
        fused = self._rrf_fuse(
            vector_results=vector_results,
            fts_results=fts_results,
            vector_weight=vector_weight,
            text_weight=text_weight,
            rrf_k=rrf_k,
            score_threshold=score_threshold,
        )

        # 5. 返回 top_k
        results = fused[:top_k]
        logger.info("混合搜索完成，返回 %d 条结果", len(results))
        return results

    async def _vector_search(
        self,
        embedding_str: str,
        space_id: uuid.UUID,
        fetch_k: int,
    ) -> list[SearchResult]:
        """向量语义搜索"""
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
            LIMIT :fetch_k
            """
        )
        result = await self.db.execute(
            sql,
            {"query_embedding": embedding_str, "space_id": space_id, "fetch_k": fetch_k},
        )
        return [
            SearchResult(
                chunk_id=row.id,
                document_id=row.document_id,
                content=row.content,
                score=row.score,
                metadata=row.chunk_metadata or {},
                document_title=row.document_title,
                document_filename=row.document_filename,
            )
            for row in result.fetchall()
        ]

    async def _fulltext_search(
        self,
        tsquery_str: str,
        space_id: uuid.UUID,
        fetch_k: int,
    ) -> list[SearchResult]:
        """PostgreSQL 全文检索"""
        if not tsquery_str.strip():
            return []

        sql = text(
            """
            SELECT
                dc.id,
                dc.document_id,
                dc.content,
                dc.chunk_metadata,
                ts_rank(dc.content_tsv, to_tsquery('simple', :query_tsv)) as fts_score,
                sd.title as document_title,
                sd.original_filename as document_filename
            FROM document_chunks dc
            JOIN space_documents sd ON dc.document_id = sd.id
            WHERE dc.space_id = :space_id
              AND dc.content_tsv IS NOT NULL
              AND dc.content_tsv @@ to_tsquery('simple', :query_tsv)
            ORDER BY fts_score DESC
            LIMIT :fetch_k
            """
        )
        result = await self.db.execute(
            sql,
            {"query_tsv": tsquery_str, "space_id": space_id, "fetch_k": fetch_k},
        )
        return [
            SearchResult(
                chunk_id=row.id,
                document_id=row.document_id,
                content=row.content,
                score=row.fts_score,
                metadata=row.chunk_metadata or {},
                document_title=row.document_title,
                document_filename=row.document_filename,
            )
            for row in result.fetchall()
        ]

    @staticmethod
    def _rrf_fuse(
        vector_results: list[SearchResult],
        fts_results: list[SearchResult],
        vector_weight: float,
        text_weight: float,
        rrf_k: int,
        score_threshold: float,
    ) -> list[SearchResult]:
        """
        Reciprocal Rank Fusion (RRF) 融合两路搜索结果。

        score(d) = vector_weight / (rrf_k + rank_v) + text_weight / (rrf_k + rank_t)
        """
        # 收集所有 chunk，以 chunk_id 为 key
        chunk_map: dict[uuid.UUID, SearchResult] = {}
        vector_ranks: dict[uuid.UUID, int] = {}
        fts_ranks: dict[uuid.UUID, int] = {}

        for rank, result in enumerate(vector_results, start=1):
            # 过滤低于阈值的向量结果
            if result.score < score_threshold:
                continue
            chunk_map[result.chunk_id] = result
            vector_ranks[result.chunk_id] = rank

        for rank, result in enumerate(fts_results, start=1):
            if result.chunk_id not in chunk_map:
                chunk_map[result.chunk_id] = result
            fts_ranks[result.chunk_id] = rank

        # 计算 RRF 分数
        scored: list[tuple[SearchResult, float]] = []
        inf = float("inf")
        for chunk_id, result in chunk_map.items():
            rank_v = vector_ranks.get(chunk_id, inf)
            rank_t = fts_ranks.get(chunk_id, inf)

            rrf_score = 0.0
            if rank_v != inf:
                rrf_score += vector_weight / (rrf_k + rank_v)
            if rank_t != inf:
                rrf_score += text_weight / (rrf_k + rank_t)

            scored.append((result, rrf_score))

        # 按 RRF 分数降序排列
        scored.sort(key=lambda x: x[1], reverse=True)

        # 返回结果，将 RRF 分数写入 score 字段
        return [
            SearchResult(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                content=r.content,
                score=rrf_score,
                metadata=r.metadata,
                document_title=r.document_title,
                document_filename=r.document_filename,
            )
            for r, rrf_score in scored
        ]
