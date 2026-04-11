"""Artifact Generation Agent - 生成交互式 HTML 教学演示"""

import logging
import re

from agents.llm.client import OpenRouterClient
from config import get_settings

logger = logging.getLogger(__name__)

# HTML 大小上限
MAX_HTML_SIZE = 500 * 1024  # 500KB

# CDN 库目录
CDN_LIBRARIES = {
    "p5": {
        "name": "p5.js",
        "url": "https://cdn.jsdelivr.net/npm/p5@1.11.3/lib/p5.min.js",
        "description": "创意编程/物理模拟/动画",
    },
    "chart": {
        "name": "Chart.js",
        "url": "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js",
        "description": "数据图表",
    },
    "d3": {
        "name": "D3.js",
        "url": "https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js",
        "description": "数据可视化",
    },
    "three": {
        "name": "Three.js",
        "url": "https://cdn.jsdelivr.net/npm/three@0.172.0/build/three.min.js",
        "description": "3D 渲染",
    },
    "katex": {
        "name": "KaTeX",
        "url": "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js",
        "css": "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css",
        "description": "数学公式渲染",
    },
    "anime": {
        "name": "anime.js",
        "url": "https://cdn.jsdelivr.net/npm/animejs@3.2.2/lib/anime.min.js",
        "description": "动画效果",
    },
}

SYSTEM_PROMPT = """你是一个交互式 HTML 教学演示生成器。你的任务是生成一个完整的、可独立运行的 HTML 文件，用于教学目的。

## 要求

1. **输出格式**: 输出完整的单文件 HTML（包含内联 CSS 和 JS）。不要输出 markdown code fence，直接输出 HTML 代码。
2. **CDN 库**: 如果需要外部库，仅使用以下 CDN 地址：
{library_list}
3. **页面设计**:
   - 响应式布局，适配 iframe 嵌入
   - 深色背景（#1a1a2e 或类似暗色），文字使用浅色
   - 字体使用系统默认无衬线字体
   - 美观的 UI，适当使用圆角、阴影、渐变
4. **安全限制**:
   - 禁止使用 fetch/XMLHttpRequest 发起网络请求
   - 禁止使用 localStorage/sessionStorage
   - 禁止访问 parent/top 框架
5. **交互性**: 内容应当是交互式的，用户可以操作、探索、实验
6. **教学导向**: 包含清晰的标题、说明文字，帮助用户理解演示内容
7. **完整性**: HTML 必须包含 <!DOCTYPE html> 声明，是可以直接在浏览器中打开的完整页面

## 安全 Meta 标签
在 <head> 中包含：
<meta http-equiv="Content-Security-Policy" content="default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: blob:; connect-src 'none';">
"""

UPDATE_PROMPT = """你是一个交互式 HTML 教学演示生成器。用户希望更新现有的 HTML 演示。

## 现有 HTML
```html
{existing_html}
```

## 更新要求
根据用户的修改说明，生成完整的新版本 HTML。保留原有的基本结构和功能，只修改用户要求的部分。

## 输出要求
- 输出完整的单文件 HTML（不要用 markdown code fence 包裹）
- 保持原有的 CSP meta 标签和安全限制
- 保持深色主题和响应式布局
"""


def _build_library_list(libraries: list[str] | None) -> str:
    """构建 CDN 库列表文本"""
    if not libraries:
        return "（无需外部库，使用原生 HTML/CSS/JS 即可）"

    lines = []
    for lib_key in libraries:
        lib = CDN_LIBRARIES.get(lib_key)
        if lib:
            lines.append(f"- {lib['name']}: <script src=\"{lib['url']}\"></script>")
            if "css" in lib:
                lines.append(f"  CSS: <link rel=\"stylesheet\" href=\"{lib['css']}\">")
    return "\n".join(lines) if lines else "（无需外部库）"


def _extract_html(llm_output: str) -> str:
    """从 LLM 输出中提取 HTML 内容"""
    # 尝试提取 code fence 中的 HTML
    fence_match = re.search(r'```(?:html)?\s*\n(.*?)```', llm_output, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # 如果输出本身就是 HTML（以 <!DOCTYPE 或 <html 开头）
    stripped = llm_output.strip()
    if stripped.lower().startswith('<!doctype') or stripped.lower().startswith('<html'):
        return stripped

    # 尝试找到 HTML 标签范围
    html_match = re.search(r'(<!DOCTYPE.*?</html>)', llm_output, re.DOTALL | re.IGNORECASE)
    if html_match:
        return html_match.group(1).strip()

    return stripped


_CSP_TAG = '<meta http-equiv="Content-Security-Policy"'
_CSP_CONNECT_NONE = "connect-src 'none'"

# Fallback CSP to inject if LLM omitted it
_FALLBACK_CSP = (
    '<meta http-equiv="Content-Security-Policy" content="'
    "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: blob:; connect-src 'none';"
    '">'
)


def _ensure_csp(html: str) -> str:
    """Ensure CSP meta tag with connect-src 'none' is present; inject if missing."""
    lower = html.lower()
    if _CSP_CONNECT_NONE.lower() in lower:
        return html

    # Inject after <head> tag
    head_match = re.search(r'(<head[^>]*>)', html, re.IGNORECASE)
    if head_match:
        insert_pos = head_match.end()
        return html[:insert_pos] + '\n' + _FALLBACK_CSP + '\n' + html[insert_pos:]

    # No <head> tag found — inject after <!DOCTYPE ...> or at beginning
    doctype_match = re.search(r'(<!DOCTYPE[^>]*>)', html, re.IGNORECASE)
    if doctype_match:
        insert_pos = doctype_match.end()
        return html[:insert_pos] + '\n<head>\n' + _FALLBACK_CSP + '\n</head>\n' + html[insert_pos:]

    return _FALLBACK_CSP + '\n' + html


def _validate_html(html: str) -> bool:
    """基础 HTML 校验"""
    lower = html.lower()
    return '<!doctype' in lower or '<html' in lower


class ArtifactGenerationAgent:
    """生成交互式 HTML 教学演示的 Agent"""

    def __init__(self) -> None:
        settings = get_settings()
        self.llm_client = OpenRouterClient(
            model_override=settings.artifact_model
        )

    async def generate(
        self,
        description: str,
        libraries: list[str] | None = None,
        existing_html: str | None = None,
    ) -> str:
        """
        生成或更新交互式 HTML。

        Args:
            description: 用户需求描述
            libraries: 需要的 CDN 库列表（如 ["p5", "chart"]）
            existing_html: 更新时传入的现有 HTML

        Returns:
            生成的完整 HTML 字符串

        Raises:
            ValueError: HTML 校验失败或超出大小限制
        """
        if existing_html:
            system_prompt = UPDATE_PROMPT.format(
                existing_html=existing_html[:50000]  # 截断避免过长
            )
        else:
            library_list = _build_library_list(libraries)
            system_prompt = SYSTEM_PROMPT.format(library_list=library_list)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": description},
        ]

        logger.info("Artifact generation starting: desc=%s, libs=%s, update=%s",
                     description[:100], libraries, existing_html is not None)

        raw_output = await self.llm_client.complete(
            messages=messages,
            temperature=0.7,
            max_tokens=16384,
        )

        html = _extract_html(raw_output)

        if not _validate_html(html):
            raise ValueError("生成的内容不是有效的 HTML 文档")

        # Enforce CSP — inject if LLM omitted it
        html = _ensure_csp(html)

        if len(html.encode("utf-8")) > MAX_HTML_SIZE:
            raise ValueError(f"生成的 HTML 超出大小限制 ({MAX_HTML_SIZE // 1024}KB)")

        logger.info("Artifact generation complete: size=%d bytes", len(html.encode("utf-8")))
        return html
