"""RAG Tools - Document Search and Retrieval"""

import logging
from typing import Any
from uuid import UUID

from chat.tools.base import ToolResult
from config import get_settings
from db.database import get_scoped_session
from rag.retrieval.hybrid_search import HybridSearchService
from rag.retrieval.vector_search import VectorSearchService

logger = logging.getLogger(__name__)
settings = get_settings()

# Validation constants
MAX_QUERY_LENGTH = 2000
MIN_TOP_K = 1
MAX_TOP_K = 20


# ============ RAG Tool Definition (OpenAI Function Calling Format) ============

RAG_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "在用户上传的文档中搜索相关内容。当用户询问的问题可能与其上传的学习资料相关时使用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询，应该是用户问题的关键内容或相关概念",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量，默认 5",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
]


# ============ RAG Tool Executor ============


class RAGToolExecutor:
    """Executor for RAG document search tools"""

    def __init__(self, space_id: UUID) -> None:
        self.space_id = space_id

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a RAG tool and return result. Creates a short-lived DB session per call."""
        if tool_name == "search_documents":
            try:
                return await self._search_documents(arguments)
            except Exception as e:
                logger.error(f"RAG tool execution error: {e}", exc_info=True)
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"文档搜索执行错误: {e!s}",
                )

        return ToolResult(
            success=False,
            data=None,
            message=f"未知的工具: {tool_name}",
        )

    async def _search_documents(self, args: dict[str, Any]) -> ToolResult:
        """Search documents in the current learning space."""
        query = str(args.get("query", "")).strip()
        top_k = int(args.get("top_k", 5))

        # Validate query
        if not query:
            return ToolResult(
                success=False,
                data=None,
                message="搜索查询不能为空",
            )

        if len(query) > MAX_QUERY_LENGTH:
            return ToolResult(
                success=False,
                data=None,
                message=f"搜索查询过长（最大 {MAX_QUERY_LENGTH} 字符）",
            )

        # Validate top_k bounds
        top_k = min(max(top_k, MIN_TOP_K), MAX_TOP_K)

        try:
            # Use a short-lived session for the search
            async with get_scoped_session() as db:
                if settings.hybrid_search_enabled:
                    search_service = HybridSearchService(db)
                else:
                    search_service = VectorSearchService(db)
                results = await search_service.search(
                    query=query,
                    space_id=self.space_id,
                    top_k=top_k,
                    score_threshold=0.3,
                )

            if not results:
                return ToolResult(
                    success=True,
                    data={"results": [], "total": 0},
                    message="未找到相关文档内容",
                )

            formatted_results = [
                {
                    "content": result.content,
                    "source": result.document_title or result.document_filename,
                    "score": round(result.score, 3),
                    "document_id": str(result.document_id),
                    "chunk_id": str(result.chunk_id),
                    "page_number": (result.metadata or {}).get("page_number"),
                }
                for result in results
            ]

            return ToolResult(
                success=True,
                data={
                    "results": formatted_results,
                    "total": len(formatted_results),
                },
                message=f"找到 {len(formatted_results)} 条相关内容",
            )

        except Exception as e:
            logger.error(f"Document search failed: {e}", exc_info=True)
            return ToolResult(
                success=False,
                data=None,
                message=f"搜索失败: {e!s}",
            )
