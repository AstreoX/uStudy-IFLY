"""Tool Catalog - 工具注册中心、轻量目录、元工具

自动模式：LLM 仅看到轻量目录 + get_tool_details 元工具，按需加载完整定义
手动模式：用户选择启用的工具，直接注册完整定义
"""

import logging
from dataclasses import dataclass
from typing import Any

from chat.tools.base import ToolResult
from chat.tools.graph_tools import GRAPH_TOOLS
from chat.tools.quiz_generation_tools import QUIZ_GENERATION_TOOLS
from chat.tools.quiz_result_tools import QUIZ_RESULT_TOOLS
from chat.tools.web_tools import WEB_TOOLS
from chat.tools.search_tools import SEARCH_TOOLS
from chat.tools.schedule_tools import SCHEDULE_TOOLS
from chat.tools.rag_tools import RAG_TOOLS
from chat.tools.vector_memory_tools import VECTOR_MEMORY_TOOLS
from chat.tools.time_tools import TIME_TOOLS
from chat.tools.review_tools import REVIEW_TOOLS
from chat.tools.note_tools import NOTE_TOOLS
from chat.tools.artifact_tools import ARTIFACT_TOOLS
from chat.tools.image_tools import IMAGE_TOOLS

logger = logging.getLogger(__name__)


# ============ 1. TOOL_REGISTRY: 全量注册表 ============

def _build_registry() -> dict[str, dict]:
    """从所有工具列表构建 tool_name -> 完整 OpenAI tool 定义 的映射"""
    registry: dict[str, dict] = {}
    all_tool_lists = [
        GRAPH_TOOLS,
        QUIZ_GENERATION_TOOLS,
        QUIZ_RESULT_TOOLS,
        WEB_TOOLS,
        SEARCH_TOOLS,
        SCHEDULE_TOOLS,
        RAG_TOOLS,
        VECTOR_MEMORY_TOOLS,
        TIME_TOOLS,
        REVIEW_TOOLS,
        NOTE_TOOLS,
        IMAGE_TOOLS,
        ARTIFACT_TOOLS,
    ]
    for tool_list in all_tool_lists:
        for tool_def in tool_list:
            name = tool_def["function"]["name"]
            registry[name] = tool_def
    return registry


TOOL_REGISTRY: dict[str, dict] = _build_registry()


# ============ 2. TOOL_CATALOG: 轻量目录 ============

@dataclass
class ToolCatalogEntry:
    name: str       # 函数名 (e.g., "add_node")
    category: str   # 分类 (e.g., "知识图谱")
    summary: str    # 一行简述


TOOL_CATALOG: list[ToolCatalogEntry] = [
    # ── 知识图谱 (15) ──
    ToolCatalogEntry("get_graph_overview", "知识图谱", "获取知识图谱概览（节点、边、掌握度）"),
    ToolCatalogEntry("add_node", "知识图谱", "添加知识点节点"),
    ToolCatalogEntry("add_edge", "知识图谱", "添加节点关系边"),
    ToolCatalogEntry("delete_node", "知识图谱", "删除知识点节点"),
    ToolCatalogEntry("delete_edge", "知识图谱", "删除关系边"),
    ToolCatalogEntry("update_mastery", "知识图谱", "更新节点掌握度"),
    ToolCatalogEntry("get_child_nodes", "知识图谱", "获取子节点（支持递归）"),
    ToolCatalogEntry("get_parent_nodes", "知识图谱", "获取父节点"),
    ToolCatalogEntry("get_sibling_nodes", "知识图谱", "获取兄弟节点"),
    ToolCatalogEntry("generate_learning_path", "知识图谱", "根据节点序列生成学习路径"),
    ToolCatalogEntry("extend_learning_path", "知识图谱", "扩展已有学习路径（从末尾节点续接新节点）"),
    ToolCatalogEntry("get_learning_paths", "知识图谱", "获取所有学习路径"),
    ToolCatalogEntry("delete_all_learning_paths", "知识图谱", "删除所有学习路径"),
    ToolCatalogEntry("get_postorder_traversal", "知识图谱", "获取知识树子树的后序遍历"),
    ToolCatalogEntry("update_learning_path_segment", "知识图谱", "局部更新学习路径（替换首尾节点之间的区间）"),

    # ── 测验 (3) ──
    ToolCatalogEntry("generate_test", "测验", "生成正式测试题（异步）"),
    ToolCatalogEntry("view_quiz_results", "测验", "查看测验成绩列表"),
    ToolCatalogEntry("view_quiz_attempt_detail", "测验", "查看测验详细分析"),

    # ── 网络搜索 (2) ──
    ToolCatalogEntry("web_search", "网络搜索", "DuckDuckGo 网络搜索"),
    ToolCatalogEntry("web_fetch", "网络搜索", "抓取网页内容"),

    # ── 学术搜索 (3) ──
    ToolCatalogEntry("academic_search", "学术搜索", "Semantic Scholar 学术论文搜索"),
    ToolCatalogEntry("encyclopedia_search", "学术搜索", "Wikipedia 百科全书搜索"),
    ToolCatalogEntry("course_search", "学术搜索", "Bilibili 教学视频搜索"),

    # ── 日程 (4) ──
    ToolCatalogEntry("get_schedule", "日程", "查询日程安排"),
    ToolCatalogEntry("add_schedule", "日程", "添加日程事件"),
    ToolCatalogEntry("delete_schedule", "日程", "删除日程事件"),
    ToolCatalogEntry("update_schedule", "日程", "更新日程事件"),

    # ── 文档检索 (1) ──
    ToolCatalogEntry("search_documents", "文档检索", "搜索用户上传的文档"),

    # ── 记忆 (4) ──
    ToolCatalogEntry("remember", "记忆", "写入长期记忆（跨空间持久）"),
    ToolCatalogEntry("remember_space", "记忆", "写入当前学习空间记忆"),
    ToolCatalogEntry("forget", "记忆", "删除指定记忆或清空"),
    ToolCatalogEntry("search_memories", "记忆", "搜索记忆信息"),

    # ── 时间 (1) ──
    ToolCatalogEntry("get_current_time", "时间", "获取当前日期和时间"),

    # ── 复习 (2) ──
    ToolCatalogEntry("get_review_events", "复习", "查看到期/逾期的待复习项"),
    ToolCatalogEntry("mark_review_completed", "复习", "标记复习完成"),

    # ── 笔记 (5) ──
    ToolCatalogEntry("create_note", "笔记", "创建学习笔记卡片（支持 Markdown 和图片）"),
    ToolCatalogEntry("list_notes", "笔记", "查看某节点下的笔记列表（标题概览）"),
    ToolCatalogEntry("view_note_detail", "笔记", "查看笔记完整内容（带行号）"),
    ToolCatalogEntry("update_note", "笔记", "更新笔记内容（支持按行号局部替换）"),
    ToolCatalogEntry("delete_note", "笔记", "删除指定笔记"),

    # ── 图表生成 (1) ──
    ToolCatalogEntry("generate_chart", "图表生成", "根据描述生成图表或图片"),

    # ── 互动演示 (2) ──
    ToolCatalogEntry("create_artifact", "互动演示", "创建交互式 HTML 演示（每个对话仅限一个，禁止在一个对话session中重复调用）"),
    ToolCatalogEntry("update_artifact", "互动演示", "修改已有的交互式演示（对话已有 artifact 时优先使用此工具）"),
]

# 按分类组织的目录（用于 API 返回和前端展示）
TOOL_CATALOG_BY_CATEGORY: dict[str, list[ToolCatalogEntry]] = {}
for _entry in TOOL_CATALOG:
    TOOL_CATALOG_BY_CATEGORY.setdefault(_entry.category, []).append(_entry)


# ============ 3. get_tool_details 元工具 ============

GET_TOOL_DETAILS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_tool_details",
        "description": "获取指定工具的完整参数定义。调用任何工具前，必须先用此工具获取其完整定义。",
        "parameters": {
            "type": "object",
            "properties": {
                "tool_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要获取详情的工具名称列表",
                }
            },
            "required": ["tool_names"],
        },
    },
}


# 搜索相关工具名（受 search_channels 设置影响）
_SEARCH_CHANNEL_TOOL_MAP: dict[str, str] = {
    "web_search_enabled": "web_search",
    "web_fetch_enabled": "web_fetch",  # web_fetch 跟随 web_search
    "academic_search_enabled": "academic_search",
    "encyclopedia_search_enabled": "encyclopedia_search",
    "course_search_enabled": "course_search",
}

# web_search 和 web_fetch 都受 web_search_enabled 控制
_WEB_TOOL_NAMES = {"web_search", "web_fetch"}
_SEARCH_TOOL_NAMES = {"academic_search", "encyclopedia_search", "course_search"}


def execute_get_tool_details(
    tool_names: list[str],
    available_tools: list[dict],
    search_channels: dict[str, bool] | None = None,
) -> tuple[ToolResult, list[dict]]:
    """
    执行 get_tool_details 元工具。

    Args:
        tool_names: 请求的工具名称列表
        available_tools: 当前已注册的工具定义列表
        search_channels: 用户搜索频道设置

    Returns:
        (tool_result, new_tools):
        - tool_result: 包含工具 schema 描述的 ToolResult
        - new_tools: 需要追加到 available_tools 的新工具定义
    """
    channels = search_channels or {}
    already_registered = {
        t["function"]["name"] for t in available_tools
    }

    found_schemas: list[dict] = []
    new_tools: list[dict] = []
    not_found: list[str] = []

    for name in tool_names:
        # 检查搜索频道设置
        if name in _WEB_TOOL_NAMES and not channels.get("web_search_enabled", True):
            not_found.append(f"{name}（已被用户禁用）")
            continue
        if name in _SEARCH_TOOL_NAMES:
            channel_key = f"{name}_enabled"
            if not channels.get(channel_key, True):
                not_found.append(f"{name}（已被用户禁用）")
                continue

        tool_def = TOOL_REGISTRY.get(name)
        if not tool_def:
            not_found.append(name)
            continue

        # 返回 schema 供 LLM 学习参数格式
        found_schemas.append({
            "name": name,
            "description": tool_def["function"]["description"],
            "parameters": tool_def["function"]["parameters"],
        })

        # 追加到 available_tools（避免重复）
        if name not in already_registered:
            new_tools.append(tool_def)

    # 构造结果消息
    result_parts = []
    if found_schemas:
        result_parts.append(f"已加载 {len(found_schemas)} 个工具的完整定义，现在可以直接调用它们：")
        for schema in found_schemas:
            result_parts.append(f"\n### {schema['name']}")
            result_parts.append(f"描述: {schema['description']}")
            import json
            result_parts.append(f"参数: {json.dumps(schema['parameters'], ensure_ascii=False, indent=2)}")
    if not_found:
        result_parts.append(f"\n未找到以下工具: {', '.join(not_found)}")

    message = "\n".join(result_parts)
    return (
        ToolResult(
            success=len(found_schemas) > 0,
            data={"loaded_tools": [s["name"] for s in found_schemas]},
            message=message,
        ),
        new_tools,
    )


# ============ 4. 辅助函数 ============

def format_catalog_for_prompt() -> str:
    """生成系统提示词中的工具目录文本（自动模式用）"""
    lines = [
        "# 可用工具目录",
        "使用任何工具前，先调用 get_tool_details([\"工具名1\", \"工具名2\"]) 获取完整参数定义。",
        "可以一次请求多个工具的定义。",
        "",
    ]
    for category, entries in TOOL_CATALOG_BY_CATEGORY.items():
        lines.append(f"## {category}")
        for entry in entries:
            lines.append(f"- {entry.name}: {entry.summary}")
        lines.append("")

    return "\n".join(lines)


def get_tools_for_manual_mode(
    enabled_tool_names: list[str] | None,
    search_channels: dict[str, bool] | None = None,
) -> list[dict]:
    """
    返回手动模式下的完整工具定义列表。

    Args:
        enabled_tool_names: 用户启用的工具名称列表。None 表示全部启用。
        search_channels: 用户搜索频道设置

    Returns:
        完整工具定义列表
    """
    channels = search_channels or {}

    # None 表示全部启用
    if enabled_tool_names is None:
        names = set(TOOL_REGISTRY.keys())
    else:
        names = set(enabled_tool_names)

    tools = []
    for name in names:
        # 检查搜索频道设置
        if name in _WEB_TOOL_NAMES and not channels.get("web_search_enabled", True):
            continue
        if name in _SEARCH_TOOL_NAMES:
            channel_key = f"{name}_enabled"
            if not channels.get(channel_key, True):
                continue

        tool_def = TOOL_REGISTRY.get(name)
        if tool_def:
            tools.append(tool_def)

    return tools


def get_catalog_for_api() -> list[dict]:
    """返回按分类组织的工具目录（供 API 返回给前端）"""
    result = []
    for category, entries in TOOL_CATALOG_BY_CATEGORY.items():
        result.append({
            "category": category,
            "tools": [
                {"name": e.name, "summary": e.summary}
                for e in entries
            ],
        })
    return result
