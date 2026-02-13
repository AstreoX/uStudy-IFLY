"""Web Search Tools - Definitions and Executor"""

import asyncio
import html
import ipaddress
import logging
import re
import socket
from typing import Any
from urllib.parse import urlparse

import httpx
from ddgs import DDGS

from chat.tools.base import ToolResult
from config import get_settings

logger = logging.getLogger(__name__)


# ============ Constants ============

MAX_QUERY_LENGTH = 500
MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5MB

# SSRF protection - blocked hosts and IP ranges
BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "[::1]",
}

BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),       # Private
    ipaddress.ip_network("172.16.0.0/12"),    # Private
    ipaddress.ip_network("192.168.0.0/16"),   # Private
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local / Cloud metadata
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
]


# ============ 2 Web Search Tools (OpenAI Function Calling Format) ============


WEB_TOOLS: list[dict[str, Any]] = [
    # 1. web_search
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "使用搜索引擎查询关键词，返回与学习主题相关的网页搜索结果",
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
            "description": "抓取指定 URL 的网页内容，提取主要文本供学习参考",
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
]


# ============ URL Safety Validation (SSRF Protection) ============


def _is_safe_url(url: str) -> tuple[bool, str]:
    """
    Validate URL is safe to fetch (SSRF prevention).

    Args:
        url: The URL to validate

    Returns:
        Tuple of (is_safe, error_message)
    """
    try:
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme not in ("http", "https"):
            return False, "URL 必须使用 http 或 https 协议"

        # Check host exists
        hostname = parsed.hostname
        if not hostname:
            return False, "URL 格式无效：缺少主机名"

        # Check against blocked hosts
        if hostname.lower() in BLOCKED_HOSTS:
            return False, "不允许访问内部主机"

        # Resolve hostname and check IP ranges
        try:
            resolved_ip = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(resolved_ip)
            for blocked_range in BLOCKED_IP_RANGES:
                if ip in blocked_range:
                    return False, "不允许访问内部 IP 地址段"
        except socket.gaierror:
            return False, "无法解析主机名"
        except ValueError:
            # Not a valid IP address format, but hostname resolved
            pass

        return True, ""

    except Exception as e:
        return False, f"URL 格式无效: {str(e)}"


# ============ Web Tool Executor ============


class WebToolExecutor:
    """Executor for web search tools"""

    def __init__(self) -> None:
        settings = get_settings()
        self.timeout = settings.web_search_timeout_seconds
        self.default_max_length = settings.web_fetch_max_length

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
        """Execute web search using DuckDuckGo"""
        query = args.get("query", "").strip()
        max_results = min(max(args.get("max_results", 5), 1), 10)

        if not query:
            return ToolResult(
                success=False,
                data=None,
                message="搜索关键词不能为空",
            )

        # Query length validation
        if len(query) > MAX_QUERY_LENGTH:
            return ToolResult(
                success=False,
                data=None,
                message=f"搜索关键词过长（最大 {MAX_QUERY_LENGTH} 字符）",
            )

        logger.info(f"Web search: query={query[:50]}..., max_results={max_results}")

        # DuckDuckGo search is synchronous, use asyncio.to_thread
        try:
            results = await asyncio.to_thread(
                lambda: list(DDGS().text(query, max_results=max_results))
            )
        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return ToolResult(
                success=False,
                data=None,
                message="搜索服务暂时不可用，请稍后重试",
            )

        # Format results
        formatted = [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]

        logger.info(f"Web search completed: {len(formatted)} results")

        return ToolResult(
            success=True,
            data={"results": formatted, "query": query},
            message=f"找到 {len(formatted)} 条搜索结果",
        )

    async def _web_fetch(self, args: dict) -> ToolResult:
        """Fetch and extract content from URL"""
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

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            # Use streaming to check size before loading entirely
            async with client.stream(
                "GET",
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            ) as response:
                response.raise_for_status()

                # Check content type
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type and "text/plain" not in content_type:
                    return ToolResult(
                        success=False,
                        data=None,
                        message=f"不支持的内容类型: {content_type.split(';')[0]}",
                    )

                # Check content-length header if present
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_RESPONSE_SIZE:
                    return ToolResult(
                        success=False,
                        data=None,
                        message="网页内容过大，无法获取",
                    )

                # Read with size limit
                chunks = []
                total_size = 0
                async for chunk in response.aiter_bytes():
                    total_size += len(chunk)
                    if total_size > MAX_RESPONSE_SIZE:
                        return ToolResult(
                            success=False,
                            data=None,
                            message="网页内容超过大小限制",
                        )
                    chunks.append(chunk)

                html_content = b"".join(chunks).decode("utf-8", errors="replace")

        title = self._extract_title(html_content)
        content = self._extract_text(html_content, max_length)

        logger.info(f"Web fetch completed: {len(content)} chars")

        return ToolResult(
            success=True,
            data={
                "url": url,
                "title": title,
                "content": content,
                "length": len(content),
            },
            message=f"成功获取网页内容，共 {len(content)} 字符",
        )

    def _extract_title(self, html_content: str) -> str:
        """
        Extract title from HTML.

        Args:
            html_content: Raw HTML content

        Returns:
            Page title or empty string if not found
        """
        match = re.search(r"<title[^>]*>([^<]+)</title>", html_content, re.IGNORECASE)
        if match:
            return html.unescape(match.group(1).strip())
        return ""

    def _extract_text(self, html_content: str, max_length: int) -> str:
        """
        Extract main text from HTML using regex.

        Strategy:
        1. Remove script and style tags with their content
        2. Remove HTML comments
        3. Remove non-content sections (head, nav, header, footer)
        4. Remove HTML tags, keep text
        5. Decode HTML entities
        6. Clean up whitespace
        7. Truncate to max_length

        Args:
            html_content: Raw HTML content
            max_length: Maximum length of extracted text

        Returns:
            Extracted and cleaned text content
        """
        text = html_content

        # Remove script tags and content
        text = re.sub(
            r"<script[^>]*>[\s\S]*?</script>",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # Remove style tags and content
        text = re.sub(
            r"<style[^>]*>[\s\S]*?</style>",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # Remove HTML comments
        text = re.sub(r"<!--[\s\S]*?-->", "", text)

        # Remove head section
        text = re.sub(
            r"<head[^>]*>[\s\S]*?</head>",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # Remove nav, header, footer sections (common non-content areas)
        for tag in ["nav", "header", "footer", "aside", "noscript"]:
            text = re.sub(
                rf"<{tag}[^>]*>[\s\S]*?</{tag}>",
                "",
                text,
                flags=re.IGNORECASE,
            )

        # Replace block elements with newlines
        text = re.sub(r"<(p|div|br|h[1-6]|li|tr)[^>]*>", "\n", text, flags=re.IGNORECASE)

        # Remove all remaining HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Decode HTML entities (handles all entities including &nbsp;, &amp;, etc.)
        text = html.unescape(text)

        # Clean up whitespace
        text = re.sub(r"[ \t]+", " ", text)  # Multiple spaces to single
        text = re.sub(r"\n\s*\n", "\n\n", text)  # Multiple newlines to double
        text = text.strip()

        # Truncate to max_length
        if len(text) > max_length:
            # Try to cut at sentence boundary
            truncated = text[:max_length]
            last_period = truncated.rfind("。")
            last_newline = truncated.rfind("\n")
            cut_point = max(last_period, last_newline)
            if cut_point > max_length * 0.7:
                text = text[: cut_point + 1] + "..."
            else:
                text = truncated + "..."

        return text
