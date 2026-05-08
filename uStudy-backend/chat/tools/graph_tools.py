"""Knowledge Graph Tools - Definitions and Executor"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import delete as sa_delete

from chat.tools.base import ToolResult
from db.database import get_scoped_session
from db.models import Edge, EdgeType
from graph.service import GraphService
from graph.exceptions import (
    NodeNotFoundError,
    EdgeNotFoundError,
    DuplicateNodeError,
    DuplicateEdgeError,
)

logger = logging.getLogger(__name__)

_NODE_NOT_FOUND_HINT = "节点名称必须与知识图谱中已有节点完全匹配，请先调用 get_graph_overview 查看所有节点。"


# ============ 15 Knowledge Graph Tools (OpenAI Function Calling Format) ============


GRAPH_TOOLS: list[dict[str, Any]] = [
    # 1. get_graph_overview
    {
        "type": "function",
        "function": {
            "name": "get_graph_overview",
            "description": "获取当前学习空间的知识图谱概览，返回所有节点（含掌握分）和边",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    # 2. add_node
    {
        "type": "function",
        "function": {
            "name": "add_node",
            "description": "添加新的知识点节点到知识图谱",
            "parameters": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "知识点名称",
                    },
                    "mastery": {
                        "type": "integer",
                        "description": "初始掌握分（0-100），-1 表示未学习",
                        "default": -1,
                    },
                },
                "required": ["label"],
            },
        },
    },
    # 3. add_edge
    {
        "type": "function",
        "function": {
            "name": "add_edge",
            "description": "添加节点之间的关系边",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_node": {
                        "type": "string",
                        "description": "起始节点名称",
                    },
                    "to_node": {
                        "type": "string",
                        "description": "目标节点名称",
                    },
                    "edge_type": {
                        "type": "string",
                        "enum": ["knowledge_tree", "learning_path", "advanced"],
                        "description": "边类型：knowledge_tree=知识树结构，learning_path=学习路径，advanced=进阶补充",
                        "default": "advanced",
                    },
                },
                "required": ["from_node", "to_node"],
            },
        },
    },
    # 4. delete_node
    {
        "type": "function",
        "function": {
            "name": "delete_node",
            "description": "删除知识点节点及其所有相关的边",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "要删除的节点名称",
                    },
                },
                "required": ["node_name"],
            },
        },
    },
    # 5. delete_edge
    {
        "type": "function",
        "function": {
            "name": "delete_edge",
            "description": "删除一条关系边",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_node": {
                        "type": "string",
                        "description": "边的起始节点名称",
                    },
                    "to_node": {
                        "type": "string",
                        "description": "边的目标节点名称",
                    },
                },
                "required": ["from_node", "to_node"],
            },
        },
    },
    # 6. update_mastery
    {
        "type": "function",
        "function": {
            "name": "update_mastery",
            "description": "更新指定节点的掌握分",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "节点名称",
                    },
                    "mastery": {
                        "type": "integer",
                        "description": "新的掌握分（0-100）",
                        "minimum": 0,
                        "maximum": 100,
                    },
                },
                "required": ["node_name", "mastery"],
            },
        },
    },
    # 7. get_child_nodes
    {
        "type": "function",
        "function": {
            "name": "get_child_nodes",
            "description": "获取指定节点的子节点（该节点指向的节点），支持递归获取多层子节点",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "节点名称",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "最大深度，-1 表示无限深度",
                        "default": -1,
                    },
                },
                "required": ["node_name"],
            },
        },
    },
    # 8. get_parent_nodes
    {
        "type": "function",
        "function": {
            "name": "get_parent_nodes",
            "description": "获取指定节点的父节点（指向该节点的节点）",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "节点名称",
                    },
                },
                "required": ["node_name"],
            },
        },
    },
    # 9. get_sibling_nodes
    {
        "type": "function",
        "function": {
            "name": "get_sibling_nodes",
            "description": "获取指定节点的兄弟节点（有共同父节点的节点）",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "节点名称",
                    },
                },
                "required": ["node_name"],
            },
        },
    },
    # 10. generate_learning_path
    {
        "type": "function",
        "function": {
            "name": "generate_learning_path",
            "description": "根据输入的节点序列生成学习路径，在相邻节点间创建 learning_path 类型的边",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_sequence": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "节点名称序列（字符串数组），如 [\"数组\", \"链表\", \"栈\"]",
                    },
                },
                "required": ["node_sequence"],
            },
        },
    },
    # 11. extend_learning_path
    {
        "type": "function",
        "function": {
            "name": "extend_learning_path",
            "description": "扩展已有学习路径。序列的第一个节点必须是当前路径的末尾节点，后续为新增节点。例如当前路径为 A→B→C，传入 'C,D,E' 即可扩展为 A→B→C→D→E",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_sequence": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "节点名称序列（字符串数组）。第一个必须是现有路径末尾节点，如 [\"C\", \"D\", \"E\"]",
                    },
                },
                "required": ["node_sequence"],
            },
        },
    },
    # 12. get_learning_paths
    {
        "type": "function",
        "function": {
            "name": "get_learning_paths",
            "description": "获取当前学习空间的所有学习路径，返回格式化的路径列表",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    # 12. delete_all_learning_paths
    {
        "type": "function",
        "function": {
            "name": "delete_all_learning_paths",
            "description": "删除当前学习空间的所有学习路径（learning_path 类型的边）",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    # 13. get_postorder_traversal
    {
        "type": "function",
        "function": {
            "name": "get_postorder_traversal",
            "description": "获取指定节点的知识树子树的后序遍历结果。只使用 knowledge_tree 类型的边构建子树，先访问所有子节点，最后访问根节点。返回格式：节点1->节点2->节点3",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "根节点名称",
                    },
                },
                "required": ["node_name"],
            },
        },
    },
    # 14. update_learning_path_segment
    {
        "type": "function",
        "function": {
            "name": "update_learning_path_segment",
            "description": "局部更新学习路径的某段区间。传入子路径序列，首尾节点必须是原路径中已有的节点，工具会替换首尾之间的区间。例如：原路径 A→B→C，传入 'B,D,C' 后变为 A→B→D→C。",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_sequence": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "子路径节点序列（字符串数组）。首尾必须是原路径已有节点，中间可以是新节点。如 [\"B\", \"D\", \"E\", \"C\"]",
                    },
                },
                "required": ["node_sequence"],
            },
        },
    },
]


# ============ Helper Functions for Text Formatting ============


def _format_mastery(mastery: int | None) -> str:
    """将 mastery (0-100 或 None) 转换为显示格式 (0-1)"""
    if mastery is None:
        return "0"
    value = mastery / 100.0
    if value == int(value):
        return str(int(value))
    return f"{value:.2g}"


def _build_children_text(
    node_name: str, node_mastery: int | None, children: list[dict]
) -> str:
    """构建子节点树形文本"""
    lines = [f"/children_of: {node_name}"]

    # 添加目标节点作为根
    mastery = _format_mastery(node_mastery)
    lines.append(f"* {node_name} [{mastery}]")

    # 递归构建子树
    def build_subtree(nodes: list[dict], depth: int) -> None:
        for node in nodes:
            asterisks = "*" * (depth + 1)
            m = _format_mastery(node.get("mastery"))
            lines.append(f"{asterisks} {node['label']} [{m}]")
            if node.get("children"):
                build_subtree(node["children"], depth + 1)

    build_subtree(children, 1)
    return "\n".join(lines)


def _build_parents_text(node_name: str, parents: list[dict]) -> str:
    """构建父节点列表文本"""
    lines = [f"/parents_of: {node_name}"]

    if not parents:
        lines.append("(无父节点)")
    else:
        for p in parents:
            m = _format_mastery(p.get("mastery"))
            lines.append(f"- {p['label']} [{m}]")

    return "\n".join(lines)


def _build_siblings_text(node_name: str, siblings: list[dict]) -> str:
    """构建兄弟节点列表文本"""
    lines = [f"/siblings_of: {node_name}"]

    if not siblings:
        lines.append("(无兄弟节点)")
    else:
        for s in siblings:
            m = _format_mastery(s.get("mastery"))
            lines.append(f"- {s['label']} [{m}]")

    return "\n".join(lines)


def build_learning_path_chain(
    edges: list[dict],
    node_by_id: dict[str, dict],
    with_index: bool = False,
) -> str:
    """将 learning_path 边构建成链式格式：A->B->C

    Args:
        edges: learning_path 类型的边列表
        node_by_id: 节点 ID 到节点的映射
        with_index: 是否添加编号前缀（学习路径1：A->B->C）

    Returns:
        格式化的路径字符串
    """
    if not edges:
        return ""

    # 构建 from -> to 映射
    next_node: dict[str, str] = {}
    has_prev: set[str] = set()
    for edge in edges:
        from_id = edge["from_node_id"]
        to_id = edge["to_node_id"]
        next_node[from_id] = to_id
        has_prev.add(to_id)

    # 找起点（没有前驱的节点）
    starts = set(next_node.keys()) - has_prev

    # 构建每条路径
    paths = []
    for start_id in starts:
        chain = []
        current = start_id
        visited: set[str] = set()
        while current and current not in visited:
            visited.add(current)
            node = node_by_id.get(current)
            if node:
                mastery = _format_mastery(node.get("mastery"))
                chain.append(f"{node['label']}[{mastery}]")
            current = next_node.get(current)
        if chain:
            paths.append("->".join(chain))

    if with_index:
        indexed_paths = [
            f"学习路径{i + 1}：{path}" for i, path in enumerate(paths)
        ]
        return "\n".join(indexed_paths)
    return "\n".join(paths)


def build_knowledge_tree_text(
    nodes: list[dict],
    edges: list[dict],
) -> str:
    """构建紧凑文本格式的知识图谱概览"""
    if not nodes:
        return "(空知识图谱)"

    # 构建查找表
    node_by_id = {n["id"]: n for n in nodes}

    # 按类型分离边
    knowledge_tree_edges = []
    advanced_edges = []
    learning_path_edges = []
    for edge in edges:
        edge_type = edge.get("type")
        if edge_type == "knowledge_tree":
            knowledge_tree_edges.append(edge)
        elif edge_type == "advanced":
            advanced_edges.append(edge)
        elif edge_type == "learning_path":
            learning_path_edges.append(edge)

    # 构建父->子映射
    children_by_parent: dict[str, list[str]] = {}
    nodes_with_parent: set[str] = set()
    for edge in knowledge_tree_edges:
        parent_id = edge["from_node_id"]
        child_id = edge["to_node_id"]
        children_by_parent.setdefault(parent_id, []).append(child_id)
        nodes_with_parent.add(child_id)

    # 找根节点
    root_ids = set(node_by_id.keys()) - nodes_with_parent

    # DFS 构建树文本
    tree_lines: list[str] = []
    visited: set[str] = set()

    def dfs_build(node_id: str, depth: int) -> None:
        if node_id in visited:
            return
        visited.add(node_id)
        node = node_by_id.get(node_id)
        if not node:
            return
        asterisks = "*" * depth
        mastery = _format_mastery(node.get("mastery"))
        tree_lines.append(f"{asterisks} {node['label']} [{mastery}]")
        for child_id in children_by_parent.get(node_id, []):
            dfs_build(child_id, depth + 1)

    for root_id in sorted(root_ids):
        dfs_build(root_id, 1)

    # 组装结果
    result_parts = ["/basic_knowledge_tree"]
    result_parts.extend(tree_lines)

    if advanced_edges:
        result_parts.append("/advanced_knowledge_connections")
        for edge in advanced_edges:
            from_node = node_by_id.get(edge["from_node_id"])
            to_node = node_by_id.get(edge["to_node_id"])
            if from_node and to_node:
                result_parts.append(f"{from_node['label']}->{to_node['label']}")

    if learning_path_edges:
        result_parts.append("/learning_path")
        path_text = build_learning_path_chain(learning_path_edges, node_by_id)
        if path_text:
            result_parts.append(path_text)

    return "\n".join(result_parts)


# ============ Graph Tool Executor ============


class GraphToolExecutor:
    """Executor for knowledge graph tools"""

    _STRUCTURE_TOOLS = frozenset({"add_node", "delete_node", "add_edge", "delete_edge", "expand_node"})

    def __init__(self, space_id: UUID, user_id: UUID | None = None, is_collaborative: bool = False, can_edit_graph: bool = False) -> None:
        self.space_id = space_id
        self.user_id = user_id
        self.is_collaborative = is_collaborative
        self.can_edit_graph = can_edit_graph

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """
        Execute a graph tool and return result.

        Each call creates a short-lived DB session that is released immediately
        after the tool finishes, preventing SSE streams from holding connections.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments from LLM

        Returns:
            ToolResult with success status, data, and message
        """
        method_map = {
            "get_graph_overview": self._get_graph_overview,
            "add_node": self._add_node,
            "add_edge": self._add_edge,
            "delete_node": self._delete_node,
            "delete_edge": self._delete_edge,
            "update_mastery": self._update_mastery,
            "get_child_nodes": self._get_child_nodes,
            "get_parent_nodes": self._get_parent_nodes,
            "get_sibling_nodes": self._get_sibling_nodes,
            "generate_learning_path": self._generate_learning_path,
            "extend_learning_path": self._extend_learning_path,
            "get_learning_paths": self._get_learning_paths,
            "delete_all_learning_paths": self._delete_all_learning_paths,
            "get_postorder_traversal": self._get_postorder_traversal,
            "update_learning_path_segment": self._update_learning_path_segment,
        }

        handler = method_map.get(tool_name)
        if not handler:
            return ToolResult(
                success=False,
                data=None,
                message=f"未知的工具: {tool_name}",
            )

        if self.is_collaborative and not self.can_edit_graph and tool_name in self._STRUCTURE_TOOLS:
            return ToolResult(
                success=False,
                data=None,
                message="权限不足：只有空间管理员可以修改知识图谱结构（增删节点和边）。你可以更新掌握度或管理自己的学习路径。",
            )

        try:
            async with get_scoped_session() as db:
                graph_service = GraphService(db)
                return await handler(arguments, graph_service)
        except NodeNotFoundError as e:
            logger.warning(f"Node not found: {e}")
            return ToolResult(success=False, data=None, message=f"节点不存在: {e}。{_NODE_NOT_FOUND_HINT}")
        except EdgeNotFoundError as e:
            logger.warning(f"Edge not found: {e}")
            return ToolResult(success=False, data=None, message=f"边不存在: {e}")
        except DuplicateNodeError as e:
            logger.warning(f"Duplicate node: {e}")
            return ToolResult(success=False, data=None, message=f"节点已存在: {e}")
        except DuplicateEdgeError as e:
            logger.warning(f"Duplicate edge: {e}")
            return ToolResult(success=False, data=None, message=f"边已存在: {e}")
        except ValueError as e:
            logger.warning(f"Invalid value: {e}")
            return ToolResult(success=False, data=None, message=f"参数错误: {e}")
        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            return ToolResult(success=False, data=None, message=f"执行错误: {str(e)}")

    async def _get_graph_overview(self, args: dict, graph_service: GraphService) -> ToolResult:
        """Get knowledge graph overview in compact text format"""
        graph = await graph_service.get_graph(self.space_id, user_id=self.user_id, is_collaborative=self.is_collaborative)
        node_count = len(graph["nodes"])
        edge_count = len(graph["edges"])

        if node_count == 0:
            return ToolResult(
                success=True,
                data="(空知识图谱)",
                message="知识图谱为空",
            )

        overview_text = build_knowledge_tree_text(graph["nodes"], graph["edges"])

        format_explanation = """格式说明:
- /basic_knowledge_tree: 知识树结构，*数量=层级深度，[分数]=掌握度(0-1)
- /advanced_knowledge_connections: 进阶关联，A->B 表示 A 连接到 B
- /learning_path: 学习路径，A->B->C 表示建议的学习顺序

"""

        return ToolResult(
            success=True,
            data=format_explanation + overview_text,
            message=f"知识图谱概览：{node_count} 个节点，{edge_count} 条边",
        )

    async def _add_node(self, args: dict, graph_service: GraphService) -> ToolResult:
        """Add a new node"""
        label = args.get("label", "")
        if not label:
            return ToolResult(
                success=False, data=None, message="节点名称不能为空"
            )

        mastery = args.get("mastery", -1)
        # -1 means not learned, convert to None for database
        mastery_value = None if mastery == -1 else mastery

        node = await graph_service.create_node(
            space_id=self.space_id,
            label=label,
            mastery=mastery_value,
        )

        return ToolResult(
            success=True,
            data={
                "id": str(node.id),
                "label": node.label,
                "mastery": node.mastery,
            },
            message=f"成功创建节点: {label}。提示：请使用 add_edge 工具将此节点与知识图谱中的相关节点建立连接。",
        )

    async def _add_edge(self, args: dict, graph_service: GraphService) -> ToolResult:
        """Add a new edge"""
        from_node = args.get("from_node", "")
        to_node = args.get("to_node", "")
        edge_type = args.get("edge_type", "advanced")

        if not from_node or not to_node:
            return ToolResult(
                success=False, data=None, message="起始节点和目标节点名称不能为空"
            )

        # 根据名称查找节点
        from_node_obj = await graph_service.get_node_by_label(
            self.space_id, from_node
        )
        if not from_node_obj:
            return ToolResult(
                success=False, data=None, message=f"节点不存在: {from_node}。{_NODE_NOT_FOUND_HINT}"
            )

        to_node_obj = await graph_service.get_node_by_label(
            self.space_id, to_node
        )
        if not to_node_obj:
            return ToolResult(
                success=False, data=None, message=f"节点不存在: {to_node}。{_NODE_NOT_FOUND_HINT}"
            )

        edge = await graph_service.create_edge(
            space_id=self.space_id,
            from_node_id=from_node_obj.id,
            to_node_id=to_node_obj.id,
            edge_type=edge_type,
        )

        return ToolResult(
            success=True,
            data={
                "id": str(edge.id),
                "from_node": from_node,
                "to_node": to_node,
                "type": edge.type.value,
            },
            message=f"成功创建边: {from_node} -> {to_node}",
        )

    async def _delete_node(self, args: dict, graph_service: GraphService) -> ToolResult:
        """Delete a node and its edges"""
        node_name = args.get("node_name", "")
        if not node_name:
            return ToolResult(
                success=False, data=None, message="节点名称不能为空"
            )

        # 根据名称查找节点
        node = await graph_service.get_node_by_label(self.space_id, node_name)
        if not node:
            return ToolResult(
                success=False, data=None, message=f"节点不存在: {node_name}。{_NODE_NOT_FOUND_HINT}"
            )

        await graph_service.delete_node(self.space_id, node.id)

        return ToolResult(
            success=True,
            data={"deleted_node_name": node_name},
            message=f"成功删除节点: {node_name}",
        )

    async def _delete_edge(self, args: dict, graph_service: GraphService) -> ToolResult:
        """Delete an edge"""
        from_node = args.get("from_node", "")
        to_node = args.get("to_node", "")

        if not from_node or not to_node:
            return ToolResult(
                success=False, data=None, message="起始节点和目标节点名称不能为空"
            )

        # 根据名称查找节点
        from_node_obj = await graph_service.get_node_by_label(
            self.space_id, from_node
        )
        if not from_node_obj:
            return ToolResult(
                success=False, data=None, message=f"节点不存在: {from_node}。{_NODE_NOT_FOUND_HINT}"
            )

        to_node_obj = await graph_service.get_node_by_label(
            self.space_id, to_node
        )
        if not to_node_obj:
            return ToolResult(
                success=False, data=None, message=f"节点不存在: {to_node}。{_NODE_NOT_FOUND_HINT}"
            )

        # 查找边
        edge = await graph_service.get_edge_by_nodes(
            self.space_id, from_node_obj.id, to_node_obj.id
        )
        if not edge:
            return ToolResult(
                success=False,
                data=None,
                message=f"边不存在: {from_node} -> {to_node}",
            )

        await graph_service.delete_edge(self.space_id, edge.id)

        return ToolResult(
            success=True,
            data={"from_node": from_node, "to_node": to_node},
            message=f"成功删除边: {from_node} -> {to_node}",
        )

    async def _update_mastery(self, args: dict, graph_service: GraphService) -> ToolResult:
        """Update node mastery score"""
        node_name = args.get("node_name", "")
        mastery = args.get("mastery")

        if not node_name:
            return ToolResult(
                success=False, data=None, message="节点名称不能为空"
            )
        if mastery is None:
            return ToolResult(
                success=False, data=None, message="掌握分不能为空"
            )

        # 根据名称查找节点
        node = await graph_service.get_node_by_label(self.space_id, node_name)
        if not node:
            return ToolResult(
                success=False, data=None, message=f"节点不存在: {node_name}。{_NODE_NOT_FOUND_HINT}"
            )

        updated_node = await graph_service.update_mastery(
            self.space_id, node.id, mastery, user_id=self.user_id, is_collaborative=self.is_collaborative
        )

        return ToolResult(
            success=True,
            data={
                "node_name": updated_node.label,
                "mastery": updated_node.mastery,
            },
            message=f"成功更新节点 {updated_node.label} 的掌握分为 {mastery}",
        )

    async def _get_child_nodes(self, args: dict, graph_service: GraphService) -> ToolResult:
        """Get child nodes in text format"""
        node_name = args.get("node_name", "")
        max_depth = args.get("max_depth", -1)

        if not node_name:
            return ToolResult(success=False, data=None, message="节点名称不能为空")

        node = await graph_service.get_node_by_label(self.space_id, node_name)
        if not node:
            return ToolResult(success=False, data=None, message=f"节点不存在: {node_name}。{_NODE_NOT_FOUND_HINT}")

        children = await graph_service.get_children(
            self.space_id, node.id, max_depth
        )

        if not children:
            return ToolResult(
                success=True,
                data=f"/children_of: {node_name}\n(无子节点)",
                message=f"节点 {node_name} 没有子节点",
            )

        format_explanation = """格式说明:
- *数量=层级深度，[分数]=掌握度(0-1)
- 根节点为查询的目标节点

"""
        text = _build_children_text(node_name, node.mastery, children)

        return ToolResult(
            success=True,
            data=format_explanation + text,
            message=f"找到 {node_name} 的子节点树",
        )

    async def _get_parent_nodes(self, args: dict, graph_service: GraphService) -> ToolResult:
        """Get parent nodes in text format"""
        node_name = args.get("node_name", "")

        if not node_name:
            return ToolResult(success=False, data=None, message="节点名称不能为空")

        node = await graph_service.get_node_by_label(self.space_id, node_name)
        if not node:
            return ToolResult(success=False, data=None, message=f"节点不存在: {node_name}。{_NODE_NOT_FOUND_HINT}")

        parents = await graph_service.get_parents(self.space_id, node.id)

        format_explanation = """格式说明:
- 节点名 [掌握度] 表示一个父节点
- 一个节点可能有多个父节点

"""
        text = _build_parents_text(node_name, parents)

        return ToolResult(
            success=True,
            data=format_explanation + text,
            message=f"找到 {len(parents)} 个父节点",
        )

    async def _get_sibling_nodes(self, args: dict, graph_service: GraphService) -> ToolResult:
        """Get sibling nodes in text format"""
        node_name = args.get("node_name", "")

        if not node_name:
            return ToolResult(success=False, data=None, message="节点名称不能为空")

        node = await graph_service.get_node_by_label(self.space_id, node_name)
        if not node:
            return ToolResult(success=False, data=None, message=f"节点不存在: {node_name}。{_NODE_NOT_FOUND_HINT}")

        siblings = await graph_service.get_siblings(self.space_id, node.id)

        format_explanation = """格式说明:
- 节点名 [掌握度] 表示一个兄弟节点
- 兄弟节点 = 与目标节点有共同父节点的节点

"""
        text = _build_siblings_text(node_name, siblings)

        return ToolResult(
            success=True,
            data=format_explanation + text,
            message=f"找到 {len(siblings)} 个兄弟节点",
        )

    async def _generate_learning_path(self, args: dict, graph_service: GraphService) -> ToolResult:
        """Generate learning path from node sequence"""
        node_sequence = args.get("node_sequence", "")

        if not node_sequence:
            return ToolResult(
                success=False, data=None, message="节点序列不能为空"
            )

        # 解析节点名称序列
        node_names = node_sequence if isinstance(node_sequence, list) else [name.strip() for name in node_sequence.split(",")]

        if len(node_names) < 2:
            return ToolResult(
                success=False, data=None, message="学习路径至少需要 2 个节点"
            )

        # 根据名称查找所有节点
        node_ids = []
        for name in node_names:
            node = await graph_service.get_node_by_label(self.space_id, name)
            if not node:
                return ToolResult(
                    success=False, data=None, message=f"节点不存在: {name}。{_NODE_NOT_FOUND_HINT}"
                )
            node_ids.append(node.id)

        edges = await graph_service.create_learning_path(
            space_id=self.space_id, node_ids=node_ids, user_id=self.user_id
        )

        return ToolResult(
            success=True,
            data={
                "path": node_names,
                "edges_created": len(edges),
            },
            message=f"成功创建学习路径，包含 {len(node_names)} 个节点，新增 {len(edges)} 条边",
        )

    async def _extend_learning_path(self, args: dict, graph_service: GraphService) -> ToolResult:
        """Extend existing learning path from its terminal node."""
        node_sequence = args.get("node_sequence", "")

        if not node_sequence:
            return ToolResult(
                success=False, data=None, message="节点序列不能为空"
            )

        node_names = node_sequence if isinstance(node_sequence, list) else [name.strip() for name in node_sequence.split(",")]

        if len(node_names) < 2:
            return ToolResult(
                success=False, data=None, message="扩展路径至少需要 2 个节点（含衔接节点）"
            )

        # Resolve all node names to IDs
        node_ids = []
        for name in node_names:
            node = await graph_service.get_node_by_label(self.space_id, name)
            if not node:
                return ToolResult(
                    success=False, data=None, message=f"节点不存在: {name}。{_NODE_NOT_FOUND_HINT}"
                )
            node_ids.append(node.id)

        # Validate first node is a terminal node of the current learning path
        graph = await graph_service.get_graph(self.space_id)
        lp_edges = [e for e in graph["edges"] if e.get("type") == "learning_path"]

        if not lp_edges:
            return ToolResult(
                success=False, data=None,
                message="当前没有学习路径，无法扩展。请先使用 generate_learning_path 创建路径。",
            )

        # Find terminal nodes (nodes that appear as from but not as to, or only as to with no outgoing)
        from_ids = {e["from_node_id"] for e in lp_edges}
        to_ids = {e["to_node_id"] for e in lp_edges}
        # Terminal nodes: appear in the path but have no outgoing edge
        all_path_node_ids = from_ids | to_ids
        terminal_ids = all_path_node_ids - from_ids

        node_by_id = {n["id"]: n for n in graph["nodes"]}
        first_node_id = str(node_ids[0])

        if first_node_id not in terminal_ids:
            terminal_names = [
                node_by_id[tid]["label"]
                for tid in terminal_ids
                if tid in node_by_id
            ]
            return ToolResult(
                success=False, data=None,
                message=(
                    f"错误：序列的第一个节点 '{node_names[0]}' 不是当前路径末尾。"
                    f"末尾节点为：{', '.join(terminal_names)}。请修正后重试。"
                ),
            )

        edges = await graph_service.create_learning_path(
            space_id=self.space_id, node_ids=node_ids, user_id=self.user_id
        )

        return ToolResult(
            success=True,
            data={
                "path": node_names,
                "edges_created": len(edges),
            },
            message=f"成功扩展学习路径，新增 {len(node_names) - 1} 个节点，创建 {len(edges)} 条边",
        )

    async def _get_learning_paths(self, args: dict, graph_service: GraphService) -> ToolResult:
        """Get all learning paths in the space"""
        graph = await graph_service.get_graph(
            self.space_id, user_id=self.user_id, is_collaborative=self.is_collaborative
        )

        # 筛选 learning_path 类型的边
        learning_path_edges = [
            e for e in graph["edges"] if e.get("type") == "learning_path"
        ]

        if not learning_path_edges:
            return ToolResult(
                success=True,
                data="当前学习空间暂无学习路径",
                message="未找到学习路径",
            )

        # 构建 node_id -> node 映射
        node_by_id = {n["id"]: n for n in graph["nodes"]}

        # 使用带编号格式构建路径
        paths_text = build_learning_path_chain(
            learning_path_edges, node_by_id, with_index=True
        )

        # 统计路径数量
        path_count = paths_text.count("学习路径")

        # 添加格式说明
        format_hint = "格式说明：节点名称后方括号内的数值为用户掌握度(0-1)\n\n"

        return ToolResult(
            success=True,
            data=format_hint + paths_text,
            message=f"找到 {path_count} 条学习路径",
        )

    async def _delete_all_learning_paths(self, args: dict, graph_service: GraphService) -> ToolResult:
        """Delete all learning path edges in the space"""
        deleted_count = await graph_service.delete_all_learning_paths(
            self.space_id, user_id=self.user_id
        )

        if deleted_count == 0:
            return ToolResult(
                success=True,
                data={"deleted_count": 0},
                message="当前学习空间没有学习路径",
            )

        return ToolResult(
            success=True,
            data={"deleted_count": deleted_count},
            message=f"成功删除 {deleted_count} 条学习路径边",
        )

    async def _get_postorder_traversal(self, args: dict, graph_service: GraphService) -> ToolResult:
        """获取知识树子树的后序遍历"""
        node_name = args.get("node_name", "")

        if not node_name:
            return ToolResult(
                success=False,
                data=None,
                message="节点名称不能为空",
            )

        # 根据名称查找节点
        node = await graph_service.get_node_by_label(self.space_id, node_name)
        if not node:
            return ToolResult(
                success=False,
                data=None,
                message=f"节点不存在: {node_name}。{_NODE_NOT_FOUND_HINT}",
            )

        # 执行后序遍历
        traversal_labels = await graph_service.get_postorder_traversal(
            self.space_id, node.id
        )

        # 处理空子树情况
        if len(traversal_labels) == 0:
            return ToolResult(
                success=True,
                data="(空子树)",
                message=f"节点 {node_name} 不在知识树中",
            )

        # 格式化输出：节点1->节点2->节点3
        traversal_path = "->".join(traversal_labels)

        return ToolResult(
            success=True,
            data=traversal_path,
            message=f"后序遍历完成，共 {len(traversal_labels)} 个节点",
        )

    async def _update_learning_path_segment(
        self, args: dict, graph_service: GraphService
    ) -> ToolResult:
        """局部更新学习路径的某段区间"""
        node_sequence = args.get("node_sequence", "")
        if not node_sequence:
            return ToolResult(success=False, data=None, message="节点序列不能为空")

        node_names = node_sequence if isinstance(node_sequence, list) else [name.strip() for name in node_sequence.split(",")]

        if len(node_names) < 3:
            return ToolResult(
                success=False, data=None,
                message="局部更新至少需要 3 个节点（首尾锚点 + 至少1个中间节点）",
            )

        # Resolve all node names to objects
        node_objs = []
        for name in node_names:
            node = await graph_service.get_node_by_label(self.space_id, name)
            if not node:
                return ToolResult(
                    success=False, data=None,
                    message=f"节点不存在: {name}。{_NODE_NOT_FOUND_HINT}",
                )
            node_objs.append(node)

        anchor_start_id = str(node_objs[0].id)
        anchor_end_id = str(node_objs[-1].id)
        anchor_start_name = node_names[0]
        anchor_end_name = node_names[-1]

        if anchor_start_id == anchor_end_id:
            return ToolResult(
                success=False, data=None,
                message="首尾锚点不能是同一个节点",
            )

        # Get current learning path edges
        graph = await graph_service.get_graph(self.space_id)
        lp_edges = [e for e in graph["edges"] if e.get("type") == "learning_path"]

        if not lp_edges:
            return ToolResult(
                success=False, data=None,
                message="当前没有学习路径，无法局部更新。请先使用 generate_learning_path 创建路径。",
            )

        # Build from->to chain mapping
        next_map: dict[str, str] = {}
        has_prev: set[str] = set()
        for edge in lp_edges:
            next_map[edge["from_node_id"]] = edge["to_node_id"]
            has_prev.add(edge["to_node_id"])

        # Find path starts (nodes with no predecessor)
        starts = set(next_map.keys()) - has_prev

        # Rebuild each path chain and locate anchors
        target_chain: list[str] | None = None
        anchor_start_idx = -1
        anchor_end_idx = -1

        for start_id in starts:
            chain: list[str] = []
            current = start_id
            visited: set[str] = set()
            while current and current not in visited:
                visited.add(current)
                chain.append(current)
                current = next_map.get(current)

            s_idx = -1
            e_idx = -1
            for i, nid in enumerate(chain):
                if nid == anchor_start_id:
                    s_idx = i
                if nid == anchor_end_id:
                    e_idx = i

            if s_idx != -1 and e_idx != -1:
                target_chain = chain
                anchor_start_idx = s_idx
                anchor_end_idx = e_idx
                break

        # Validate anchor presence
        if target_chain is None:
            # Check which anchor is missing
            all_path_ids = set(next_map.keys()) | has_prev
            start_in_path = anchor_start_id in all_path_ids
            end_in_path = anchor_end_id in all_path_ids

            if not start_in_path and not end_in_path:
                return ToolResult(
                    success=False, data=None,
                    message=f"开头节点'{anchor_start_name}'和结尾节点'{anchor_end_name}'都不在任何学习路径中！请先调用 get_learning_paths 查看当前路径。",
                )
            if not start_in_path:
                return ToolResult(
                    success=False, data=None,
                    message=f"开头节点'{anchor_start_name}'不在任何学习路径中！请先调用 get_learning_paths 查看当前路径。",
                )
            if not end_in_path:
                return ToolResult(
                    success=False, data=None,
                    message=f"结尾节点'{anchor_end_name}'不在任何学习路径中！请先调用 get_learning_paths 查看当前路径。",
                )
            # Both in paths but different ones
            return ToolResult(
                success=False, data=None,
                message=f"开头节点'{anchor_start_name}'和结尾节点'{anchor_end_name}'不在同一条学习路径中！",
            )

        if anchor_end_idx <= anchor_start_idx:
            return ToolResult(
                success=False, data=None,
                message=f"结尾节点'{anchor_end_name}'在开头节点'{anchor_start_name}'之前，请检查顺序！",
            )

        # Collect old edge IDs to delete (from anchor_start to anchor_end)
        old_segment_ids = target_chain[anchor_start_idx:anchor_end_idx + 1]
        edge_ids_to_delete = []
        # Build edge lookup: (from_id, to_id) -> edge_id
        edge_lookup: dict[tuple[str, str], str] = {}
        for edge in lp_edges:
            edge_lookup[(edge["from_node_id"], edge["to_node_id"])] = edge["id"]

        for i in range(len(old_segment_ids) - 1):
            key = (old_segment_ids[i], old_segment_ids[i + 1])
            eid = edge_lookup.get(key)
            if eid:
                edge_ids_to_delete.append(eid)

        # Delete old edges in bulk
        if edge_ids_to_delete:
            from uuid import UUID as _UUID
            delete_uuids = [_UUID(eid) for eid in edge_ids_to_delete]
            await graph_service.db.execute(
                sa_delete(Edge).where(Edge.id.in_(delete_uuids))
            )

        # Create new sub-path edges
        new_node_ids = [node.id for node in node_objs]
        new_edges = await graph_service.create_learning_path(
            space_id=self.space_id, node_ids=new_node_ids, user_id=self.user_id
        )

        # Build updated path text for confirmation
        node_by_id = {n["id"]: n for n in graph["nodes"]}
        # Reconstruct the full chain: before anchor_start + new segment + after anchor_end
        before = target_chain[:anchor_start_idx]
        after = target_chain[anchor_end_idx + 1:]
        new_middle = [str(n.id) for n in node_objs]
        full_chain = before + new_middle + after

        path_labels = []
        for nid in full_chain:
            node_data = node_by_id.get(nid)
            if node_data:
                path_labels.append(node_data["label"])
            else:
                # Newly resolved node not in graph snapshot
                for obj in node_objs:
                    if str(obj.id) == nid:
                        path_labels.append(obj.label)
                        break

        updated_path = "→".join(path_labels)

        return ToolResult(
            success=True,
            data={
                "updated_path": path_labels,
                "edges_deleted": len(edge_ids_to_delete),
                "edges_created": len(new_edges),
            },
            message=f"成功更新学习路径：{updated_path}（删除 {len(edge_ids_to_delete)} 条旧边，创建 {len(new_edges)} 条新边）",
        )
