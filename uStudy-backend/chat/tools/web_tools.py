"""Web Search Tools - Definitions and Executor

Enhanced with:
- ContentRouter fallback chain (trafilatura → Crawl4AI → Jina Reader)
- SearXNG meta-search (→ DuckDuckGo backup)
- Deep crawl for multi-page extraction
"""

import asyncio
import logging
from typing import Any

import httpx
from ddgs import DDGS

from chat.tools.base import ToolResult
from config import get_settings
from crawler.ssrf import is_safe_url as _is_safe_url
from crawler.router import ContentRouter
from crawler.searxng_client import SearXNGSearchClient
from crawler.deep_crawler import DeepCrawler

logger = logging.getLogger(__name__)


# ============ Constants ============

MAX_QUERY_LENGTH = 500


# ============ 3 Web Tools (OpenAI Function Calling Format) ============


WEB_TOOLS: list[dict[str, Any]] = [
    # 1. web_search
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "使用搜索引擎查询关键词，返回与学习主题相关的网页搜索结果（聚合多个搜索引擎）",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "返回结果数量（1-10），默认为 5",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    # 2. web_fetch
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "抓取指定 URL 的网页内容，智能提取主要文本（支持静态页面和 JS 渲染页面）",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "目标网页 URL",
                    },
                    "max_length": {
                        "type": "integer",
                        "description": "最大内容长度（字符数），默认为 3000",
                        "default": 3000,
                    },
                },
                "required": ["url"],
            },
        },
    },
    # 3. web_crawl
    {
        "type": "function",
        "function": {
            "name": "web_crawl",
            "description": "深度爬取网站的多个页面内容，适用于文档站点、教程系列等。从起始 URL 出发，跟随同域链接 BFS 抓取。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "起始 URL",
                    },
                    "max_pages": {
                        "type": "integer",
                        "description": "最大爬取页面数（1-20），默认为 5",
                        "default": 5,
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "最大链接跟随深度（1-3），默认为 2",
                        "default": 2,
                    },
                    "url_pattern": {
                        "type": "string",
                        "description": "URL 过滤正则表达式（可选），仅爬取匹配的 URL",
                    },
                },
                "required": ["url"],
            },
        },
    },
]


# ============ Web Tool Executor ============


class WebToolExecutor:
    """Executor for web search tools"""

    def __init__(self) -> None:
        settings = get_settings()
        self.timeout = settings.web_search_timeout_seconds
        self.default_max_length = settings.web_fetch_max_length
        self._content_router = ContentRouter()
        self._searxng_client = SearXNGSearchClient()
        self._deep_crawler = DeepCrawler()

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """
        Execute a web tool and return result.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments from LLM

        Returns:
            ToolResult with success status, data, and message
        """
        method_map = {
            "web_search": self._web_search,
            "web_fetch": self._web_fetch,
            "web_crawl": self._web_crawl,
        }

        handler = method_map.get(tool_name)
        if not handler:
            return ToolResult(
                success=False,
                data=None,
                message=f"未知的工具: {tool_name}",
            )

        try:
            return await handler(arguments)
        except httpx.TimeoutException:
            logger.warning(f"Web tool timeout: {tool_name}")
            return ToolResult(
                success=False,
                data=None,
                message="请求超时，请稍后重试",
            )
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error: {e.response.status_code}")
            return ToolResult(
                success=False,
                data=None,
                message=f"HTTP 错误: {e.response.status_code}",
            )
        except Exception as e:
            logger.error(f"Web tool execution error: {e}", exc_info=True)
            return ToolResult(
                success=False,
                data=None,
                message=f"执行错误: {str(e)}",
            )

    async def _web_search(self, args: dict) -> ToolResult:
        """Execute web search: SearXNG first, DuckDuckGo backup."""
        query = args.get("query", "").strip()
        max_results = min(max(args.get("max_results", 5), 1), 10)

        if not query:
            return ToolResult(
                success=False,
                data=None,
                message="搜索关键词不能为空",
            )

        if len(query) > MAX_QUERY_LENGTH:
            return ToolResult(
                success=False,
                data=None,
                message=f"搜索关键词过长（最大 {MAX_QUERY_LENGTH} 字符）",
            )

        logger.info(f"Web search: query={query[:50]}..., max_results={max_results}")

        # Try SearXNG first
        searxng_results = await self._searxng_client.search(query, max_results=max_results)
        if searxng_results:
            formatted = [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "source": "web",
                }
                for r in searxng_results
            ]
            logger.info(f"SearXNG search completed: {len(formatted)} results")
            return ToolResult(
                success=True,
                data={"results": formatted, "query": query, "channel": "web", "engine": "searxng"},
                message=f"找到 {len(formatted)} 条搜索结果",
            )

        # Fallback to DuckDuckGo
        logger.info("SearXNG unavailable, falling back to DuckDuckGo")
        try:
            results = await asyncio.to_thread(
                lambda: list(DDGS().text(query, max_results=max_results, safesearch="on"))
            )
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                message="搜索服务暂时不可用，请稍后重试",
            )

        formatted = [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
                "source": "web",
            }
            for r in results
        ]

        logger.info(f"DuckDuckGo search completed: {len(formatted)} results")

        return ToolResult(
            success=True,
            data={"results": formatted, "query": query, "channel": "web", "engine": "duckduckgo"},
            message=f"找到 {len(formatted)} 条搜索结果",
        )

    async def _web_fetch(self, args: dict) -> ToolResult:
        """Fetch and extract content from URL using ContentRouter."""
        url = args.get("url", "").strip()
        max_length = min(max(args.get("max_length", self.default_max_length), 500), 10000)

        if not url:
            return ToolResult(
                success=False,
                data=None,
                message="URL 不能为空",
            )

        # SSRF protection - validate URL safety
        is_safe, error_msg = _is_safe_url(url)
        if not is_safe:
            return ToolResult(
                success=False,
                data=None,
                message=error_msg,
            )

        logger.info(f"Web fetch: url={url[:100]}, max_length={max_length}")

        result = await self._content_router.extract(url, max_length=max_length)
        if not result:
            return ToolResult(
                success=False,
                data=None,
                message="无法提取网页内容（所有提取方式均失败）",
            )

        logger.info(
            f"Web fetch completed via {result.extraction_method}: {len(result.content)} chars"
        )

        return ToolResult(
            success=True,
            data={
                "url": url,
                "title": result.title,
                "content": result.content,
                "length": len(result.content),
                "extraction_method": result.extraction_method,
            },
            message=f"成功获取网页内容，共 {len(result.content)} 字符（via {result.extraction_method}）",
        )

    async def _web_crawl(self, args: dict) -> ToolResult:
        """Deep crawl: BFS multi-page extraction."""
        url = args.get("url", "").strip()
        max_pages = min(max(args.get("max_pages", 5), 1), 20)
        max_depth = min(max(args.get("max_depth", 2), 1), 3)
        url_pattern = args.get("url_pattern")

        if not url:
            return ToolResult(
                success=False,
                data=None,
                message="URL 不能为空",
            )

        # SSRF protection
        is_safe, error_msg = _is_safe_url(url)
        if not is_safe:
            return ToolResult(
                success=False,
                data=None,
                message=error_msg,
            )

        settings = get_settings()
        if not settings.deep_crawl_enabled:
            return ToolResult(
                success=False,
                data=None,
                message="深度爬取功能未启用",
            )

        logger.info(
            f"Web crawl: url={url[:100]}, max_pages={max_pages}, "
            f"max_depth={max_depth}, pattern={url_pattern}"
        )

        results = await self._deep_crawler.crawl(
            url,
            max_pages=max_pages,
            max_depth=max_depth,
            url_pattern=url_pattern,
        )

        if not results:
            return ToolResult(
                success=False,
                data=None,
                message="深度爬取未获取到任何页面内容",
            )

        # Format results for LLM consumption
        pages = []
        for r in results:
            # Truncate each page to reasonable length
            content = r.content[:3000] + "..." if len(r.content) > 3000 else r.content
            pages.append({
                "url": r.url,
                "title": r.title,
                "content": content,
                "extraction_method": r.extraction_method,
            })

        logger.info(f"Web crawl completed: {len(pages)} pages from {url[:80]}")

        return ToolResult(
            success=True,
            data={
                "start_url": url,
                "pages": pages,
                "total_pages": len(pages),
            },
            message=f"成功爬取 {len(pages)} 个页面",
        )
