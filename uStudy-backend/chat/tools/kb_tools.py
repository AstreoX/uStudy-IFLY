"""Knowledge Base Tools - AI 保存网页到学习空间知识库"""

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from chat.tools.base import ToolResult
from crawler.ssrf import is_safe_url as _is_safe_url
from db.database import get_scoped_session
from documents.service import create_link

logger = logging.getLogger(__name__)


# ============ Tool Definition ============

KB_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "save_to_knowledge_base",
            "description": (
                "将网页 URL 保存到当前学习空间的知识库，自动提取内容并建立向量索引，"
                "后续可通过文档检索工具搜索。适用于保存在网络搜索/抓取中发现的有价值学习资料。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要保存的网页 URL",
                    },
                    "title": {
                        "type": "string",
                        "description": "文档标题（可选，不填则自动从网页提取）",
                    },
                },
                "required": ["url"],
            },
        },
    },
]

KB_TOOL_NAMES = frozenset(t["function"]["name"] for t in KB_TOOLS)


# ============ Executor ============


class KBToolExecutor:
    """Executor for knowledge base management tools."""

    def __init__(self, user_id: UUID, space_id: UUID) -> None:
        self.user_id = user_id
        self.space_id = space_id

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        if tool_name == "save_to_knowledge_base":
            return await self._save_to_knowledge_base(arguments)
        return ToolResult(
            success=False,
            data=None,
            message=f"未知的工具: {tool_name}",
        )

    async def _save_to_knowledge_base(self, args: dict) -> ToolResult:
        url = (args.get("url") or "").strip()
        if not url:
            return ToolResult(success=False, data=None, message="URL 不能为空")

        # SSRF protection
        is_safe, error_msg = await asyncio.to_thread(_is_safe_url, url)
        if not is_safe:
            return ToolResult(success=False, data=None, message=error_msg)

        # Derive title from URL path if not provided
        title = (args.get("title") or "").strip()
        if not title:
            path = urlparse(url).path.strip("/")
            title = (
                path.split("/")[-1].replace("-", " ").replace("_", " ")
                if path
                else url
            )

        try:
            async with get_scoped_session() as db:
                doc = await create_link(
                    db=db,
                    space_id=self.space_id,
                    user_id=self.user_id,
                    title=title,
                    url=url,
                )

            logger.info(
                "Saved URL to knowledge base: %s (doc_id=%s, space=%s)",
                url[:80],
                doc.id,
                self.space_id,
            )

            return ToolResult(
                success=True,
                data={
                    "document_id": str(doc.id),
                    "title": doc.title,
                    "url": url,
                },
                message=f"已保存到知识库: {doc.title}（后台正在自动提取内容并建立索引）",
            )
        except Exception as exc:
            logger.error("Failed to save to knowledge base: %s", exc, exc_info=True)
            return ToolResult(
                success=False,
                data=None,
                message=f"保存失败: {str(exc)}",
            )
