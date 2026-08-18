"""Multi-Channel Search Tools - Academic, Encyclopedia, Course"""

import asyncio
import logging
import re
from typing import Any
from urllib.parse import quote_plus

import httpx

from chat.tools.base import ToolResult
from config import get_settings

logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 500


# ============ 3 Search Tools (OpenAI Function Calling Format) ============

SEARCH_TOOLS: list[dict[str, Any]] = [
    # 1. academic_search
    {
        "type": "function",
        "function": {
            "name": "academic_search",
            "description": "搜索学术论文，返回论文标题、作者、年份、引用数、摘要等信息。适合需要查找学术文献、研究论文时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词（支持中英文）",
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
    # 2. encyclopedia_search
    {
        "type": "function",
        "function": {
            "name": "encyclopedia_search",
            "description": "搜索维基百科文章，返回百科条目标题、摘要片段、链接。适合需要查找概念定义、背景知识时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                    "language": {
                        "type": "string",
                        "description": "搜索语言：zh（中文）或 en（英文），默认 zh",
                        "enum": ["zh", "en"],
                        "default": "zh",
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
    # 3. course_search
    {
        "type": "function",
        "function": {
            "name": "course_search",
            "description": "搜索B站教育视频和课程，返回视频标题、UP主、时长、链接。适合需要查找教学视频、在线课程时使用。",
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
]

SEARCH_TOOL_NAMES = {"academic_search", "encyclopedia_search", "course_search"}


# ============ Search Tool Executor ============


class SearchToolExecutor:
    """Executor for multi-channel search tools (academic, encyclopedia, course)"""

    def __init__(self) -> None:
        settings = get_settings()
        self.semantic_scholar_timeout = settings.semantic_scholar_timeout
        self.wikipedia_timeout = settings.wikipedia_timeout
        self.bilibili_search_timeout = settings.bilibili_search_timeout

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Execute a search tool and return result."""
        method_map = {
            "academic_search": self._academic_search,
            "encyclopedia_search": self._encyclopedia_search,
            "course_search": self._course_search,
        }

        handler = method_map.get(tool_name)
        if not handler:
            return ToolResult(
                success=False,
                data=None,
                message=f"未知的搜索工具: {tool_name}",
            )

        try:
            return await handler(arguments)
        except httpx.TimeoutException:
            logger.warning(f"Search tool timeout: {tool_name}")
            return ToolResult(
                success=False,
                data=None,
                message="搜索请求超时，请稍后重试",
            )
        except Exception as e:
            logger.error(f"Search tool execution error: {e}", exc_info=True)
            return ToolResult(
                success=False,
                data=None,
                message=f"搜索执行错误: {str(e)}",
            )

    async def _academic_search(self, args: dict) -> ToolResult:
        """Search academic papers via OpenAlex API (primary) with Semantic Scholar fallback."""
        query = args.get("query", "").strip()
        max_results = min(max(args.get("max_results", 5), 1), 10)

        if not query:
            return ToolResult(success=False, data=None, message="搜索关键词不能为空")
        if len(query) > MAX_QUERY_LENGTH:
            return ToolResult(success=False, data=None, message=f"搜索关键词过长（最大 {MAX_QUERY_LENGTH} 字符）")

        logger.info(f"Academic search: query={query[:50]}..., max_results={max_results}")

        try:
            return await self._openalex_search(query, max_results)
        except Exception as e:
            logger.warning(f"OpenAlex failed ({e}), falling back to Semantic Scholar")
            return await self._semantic_scholar_search(query, max_results)

    async def _openalex_search(self, query: str, max_results: int) -> ToolResult:
        """Search via OpenAlex API (open access, no rate limits)."""
        url = "https://api.openalex.org/works"
        params = {
            "search": query,
            "per_page": max_results,
            "select": "title,authorships,publication_year,cited_by_count,doi,primary_location",
        }
        headers = {
            "User-Agent": "uStudy/1.0 (https://ustudy.top; contact@ustudy.top) httpx/0.27",
        }

        async with httpx.AsyncClient(timeout=self.semantic_scholar_timeout, headers=headers) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        papers = data.get("results", [])
        formatted = []
        for paper in papers:
            authorships = paper.get("authorships", [])
            authors_list = [a.get("author", {}).get("display_name", "") for a in authorships[:3]]
            authors_str = ", ".join(filter(None, authors_list))
            if len(authorships) > 3:
                authors_str += " et al."

            doi = paper.get("doi") or ""
            landing_url = (paper.get("primary_location") or {}).get("landing_page_url") or ""
            paper_url = landing_url or (f"https://doi.org/{doi.removeprefix('https://doi.org/')}" if doi else "")

            formatted.append({
                "title": paper.get("title", ""),
                "url": paper_url,
                "snippet": "",
                "source": "academic",
                "authors": authors_str,
                "year": paper.get("publication_year"),
                "citation_count": paper.get("cited_by_count", 0),
            })

        logger.info(f"OpenAlex search completed: {len(formatted)} results")

        return ToolResult(
            success=True,
            data={"results": formatted, "query": query, "channel": "academic"},
            message=f"找到 {len(formatted)} 篇学术论文",
        )

    async def _semantic_scholar_search(self, query: str, max_results: int) -> ToolResult:
        """Fallback: search via Semantic Scholar API."""
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": max_results,
            "fields": "title,authors,year,citationCount,url,abstract",
        }
        headers = {
            "User-Agent": "uStudy/1.0 (https://ustudy.top; contact@ustudy.top) httpx/0.27",
        }

        async with httpx.AsyncClient(timeout=self.semantic_scholar_timeout, headers=headers) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        papers = data.get("data", [])
        formatted = []
        for paper in papers:
            authors_list = paper.get("authors", [])
            authors_str = ", ".join(a.get("name", "") for a in authors_list[:3])
            if len(authors_list) > 3:
                authors_str += " et al."

            abstract = paper.get("abstract", "") or ""
            snippet = abstract[:200] + "..." if len(abstract) > 200 else abstract

            formatted.append({
                "title": paper.get("title", ""),
                "url": paper.get("url", ""),
                "snippet": snippet,
                "source": "academic",
                "authors": authors_str,
                "year": paper.get("year"),
                "citation_count": paper.get("citationCount", 0),
            })

        logger.info(f"Semantic Scholar search completed: {len(formatted)} results")

        return ToolResult(
            success=True,
            data={"results": formatted, "query": query, "channel": "academic"},
            message=f"找到 {len(formatted)} 篇学术论文",
        )

    async def _encyclopedia_search(self, args: dict) -> ToolResult:
        """Search Wikipedia articles."""
        query = args.get("query", "").strip()
        language = args.get("language", "zh")
        max_results = min(max(args.get("max_results", 5), 1), 10)

        if not query:
            return ToolResult(success=False, data=None, message="搜索关键词不能为空")
        if len(query) > MAX_QUERY_LENGTH:
            return ToolResult(success=False, data=None, message=f"搜索关键词过长（最大 {MAX_QUERY_LENGTH} 字符）")

        if language not in ("zh", "en"):
            language = "zh"

        logger.info(f"Encyclopedia search: query={query[:50]}..., lang={language}, max_results={max_results}")

        url = f"https://{language}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": max_results,
            "format": "json",
            "utf8": 1,
        }

        headers = {
            "User-Agent": "uStudy/1.0 (https://ustudy.top; contact@ustudy.top) httpx/0.27",
        }

        async with httpx.AsyncClient(timeout=self.wikipedia_timeout, headers=headers) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        results = data.get("query", {}).get("search", [])
        formatted = []
        for item in results:
            title = item.get("title", "")
            # Wikipedia snippets contain HTML tags, strip them
            snippet_html = item.get("snippet", "")
            snippet = re.sub(r"<[^>]+>", "", snippet_html)
            wiki_url = f"https://{language}.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}"

            formatted.append({
                "title": title,
                "url": wiki_url,
                "snippet": snippet,
                "source": "encyclopedia",
            })

        logger.info(f"Encyclopedia search completed: {len(formatted)} results")

        return ToolResult(
            success=True,
            data={"results": formatted, "query": query, "channel": "encyclopedia"},
            message=f"找到 {len(formatted)} 条百科结果",
        )

    async def _course_search(self, args: dict) -> ToolResult:
        """Search Bilibili educational videos. Falls back to DuckDuckGo if API fails."""
        query = args.get("query", "").strip()
        max_results = min(max(args.get("max_results", 5), 1), 10)

        if not query:
            return ToolResult(success=False, data=None, message="搜索关键词不能为空")
        if len(query) > MAX_QUERY_LENGTH:
            return ToolResult(success=False, data=None, message=f"搜索关键词过长（最大 {MAX_QUERY_LENGTH} 字符）")

        logger.info(f"Course search: query={query[:50]}..., max_results={max_results}")

        # Try Bilibili API first
        try:
            return await self._bilibili_search(query, max_results)
        except Exception as e:
            logger.warning(f"Bilibili API failed, falling back to DuckDuckGo: {e}")
            return await self._bilibili_fallback_search(query, max_results)

    async def _bilibili_search(self, query: str, max_results: int) -> ToolResult:
        """Search via Bilibili API."""
        import uuid

        url = "https://api.bilibili.com/x/web-interface/search/type"
        params = {
            "search_type": "video",
            "keyword": query,
            "page": 1,
            "page_size": max_results,
        }
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com",
        }
        cookies = {"buvid3": str(uuid.uuid4()) + "infoc"}

        async with httpx.AsyncClient(
            timeout=self.bilibili_search_timeout,
            headers=headers,
            cookies=cookies,
        ) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if data.get("code") != 0:
            raise ValueError(f"Bilibili API error: code={data.get('code')}, message={data.get('message')}")

        results = data.get("data", {}).get("result", [])
        formatted = []
        for item in results[:max_results]:
            title = re.sub(r"<[^>]+>", "", item.get("title", ""))
            description = item.get("description", "")[:200]
            arc_url = item.get("arcurl", "")
            if arc_url and not arc_url.startswith("http"):
                arc_url = "https:" + arc_url

            # Parse duration from "HH:MM:SS" or "MM:SS" format
            duration = item.get("duration", "")

            formatted.append({
                "title": title,
                "url": arc_url,
                "snippet": description,
                "source": "course",
                "author_name": item.get("author", ""),
                "duration": duration,
            })

        logger.info(f"Bilibili search completed: {len(formatted)} results")

        return ToolResult(
            success=True,
            data={"results": formatted, "query": query, "channel": "course"},
            message=f"找到 {len(formatted)} 个课程视频",
        )

    async def _bilibili_fallback_search(self, query: str, max_results: int) -> ToolResult:
        """Fallback: search Bilibili via DuckDuckGo."""
        from ddgs import DDGS

        site_query = f"site:bilibili.com {query}"
        try:
            results = await asyncio.to_thread(
                lambda: list(DDGS().text(site_query, max_results=max_results, safesearch="on"))
            )
        except Exception as e:
            logger.error(f"DuckDuckGo fallback also failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                message="课程搜索服务暂时不可用，请稍后重试",
            )

        formatted = [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
                "source": "course",
            }
            for r in results
        ]

        logger.info(f"Course search (DuckDuckGo fallback) completed: {len(formatted)} results")

        return ToolResult(
            success=True,
            data={"results": formatted, "query": query, "channel": "course"},
            message=f"找到 {len(formatted)} 个相关视频",
        )
