"""Cross-Encoder 重排序"""

import logging
from dataclasses import dataclass

from sentence_transformers import CrossEncoder

from config import get_settings
from rag.retrieval.vector_search import SearchResult

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class RankedResult:
    """重排序后的结果"""

    result: SearchResult
    rerank_score: float


class Reranker:
    """Cross-Encoder 重排序器"""

    _instance: "Reranker | None" = None
    _model: CrossEncoder | None = None

    def __new__(cls) -> "Reranker":
        """单例模式，避免重复加载模型"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if Reranker._model is None:
            logger.info("加载 Cross-Encoder 模型: %s", settings.rerank_model)
            Reranker._model = CrossEncoder(settings.rerank_model)
            logger.info("Cross-Encoder 模型加载完成")

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int | None = None,
    ) -> list[RankedResult]:
        """
        使用 Cross-Encoder 对搜索结果进行重排序

        Args:
            query: 原始查询
            results: 向量搜索结果列表
            top_k: 返回前 K 个结果，None 表示返回全部

        Returns:
            重排序后的结果列表
        """
        if not results:
            return []

        if top_k is None:
            top_k = settings.rerank_top_k

        # 构建 (query, passage) 对
        pairs = [(query, result.content) for result in results]

        # 使用 Cross-Encoder 计算相关性分数
        logger.info("开始重排序，共 %d 个结果", len(pairs))
        scores = Reranker._model.predict(pairs)

        # 将分数与结果配对
        ranked = [
            RankedResult(result=result, rerank_score=float(score))
            for result, score in zip(results, scores)
        ]

        # 按重排序分数降序排列
        ranked.sort(key=lambda x: x.rerank_score, reverse=True)

        # 返回 top_k 结果
        result = ranked[:top_k]
        logger.info("重排序完成，返回前 %d 个结果", len(result))

        return result


def rerank_results(
    query: str,
    results: list[SearchResult],
    top_k: int | None = None,
) -> list[RankedResult]:
    """
    便捷函数：对搜索结果进行重排序

    Args:
        query: 原始查询
        results: 向量搜索结果列表
        top_k: 返回前 K 个结果

    Returns:
        重排序后的结果列表
    """
    reranker = Reranker()
    return reranker.rerank(query, results, top_k)
