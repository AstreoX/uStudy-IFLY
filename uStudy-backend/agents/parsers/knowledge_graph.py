"""知识图谱输出解析器"""

import logging
import re
from dataclasses import dataclass

from agents.exceptions import LLMParsingError

logger = logging.getLogger(__name__)


@dataclass
class ParsedNode:
    """解析后的节点"""

    label: str
    mastery: int | None  # None 表示未知 (-1)
    level: int  # 层级深度 (1, 2, 3, ...)
    parent_label: str | None  # 父节点标签


@dataclass
class ParsedEdge:
    """解析后的边"""

    source_label: str
    target_label: str
    edge_type: str  # "knowledge_tree" 或 "advanced"


@dataclass
class ParsedKnowledgeGraph:
    """解析后的知识图谱"""

    nodes: list[ParsedNode]
    edges: list[ParsedEdge]


class KnowledgeGraphParser:
    """知识图谱输出解析器"""

    # 正则模式
    KG_BLOCK_PATTERN = re.compile(
        r"<knowledge_graph>(.*?)</knowledge_graph>",
        re.DOTALL,
    )

    TREE_SECTION_PATTERN = re.compile(
        r"/basic_knowledge_tree\s*(.*?)(?=/advanced_knowledge_connections|$)",
        re.DOTALL,
    )

    CONNECTIONS_SECTION_PATTERN = re.compile(
        r"/advanced_knowledge_connections\s*(.*?)$",
        re.DOTALL,
    )

    # 节点格式: ** 节点名称 [分数]
    # 分数可以是 -1, 0, 1, 或 0.x 格式
    NODE_PATTERN = re.compile(
        r"^(\*+)\s*(.+?)\s*\[(-?\d+(?:\.\d+)?)\]\s*$",
        re.MULTILINE,
    )

    # 边格式: 源节点 -> 目标节点
    EDGE_PATTERN = re.compile(
        r"^(.+?)\s*->\s*(.+?)\s*$",
        re.MULTILINE,
    )

    def parse(
        self,
        llm_output: str,
        root_label: str | None = None,
    ) -> ParsedKnowledgeGraph:
        """
        解析 LLM 输出为结构化知识图谱

        Args:
            llm_output: LLM 生成的原始文本
            root_label: 根节点名称（可选）。如果提供，将自动创建根节点，
                        并将所有一级节点作为其子节点。

        Returns:
            解析后的知识图谱

        Raises:
            LLMParsingError: 解析失败
        """
        # 1. 提取 <knowledge_graph> 块
        kg_match = self.KG_BLOCK_PATTERN.search(llm_output)
        if not kg_match:
            raise LLMParsingError("未找到 <knowledge_graph> 标签块")

        kg_content = kg_match.group(1)

        # 2. 解析树形结构
        nodes = self._parse_tree_section(kg_content)

        if not nodes:
            raise LLMParsingError("未找到任何知识节点")

        # 3. 如果指定了根节点名称，注入虚拟根节点
        if root_label:
            nodes = self._inject_root_node(nodes, root_label)

        # 4. 构建树形边
        edges = self._build_tree_edges(nodes)

        # 5. 解析高级连接
        advanced_edges = self._parse_connections_section(kg_content, nodes)
        edges.extend(advanced_edges)

        return ParsedKnowledgeGraph(nodes=nodes, edges=edges)

    def _parse_tree_section(self, content: str) -> list[ParsedNode]:
        """解析 /basic_knowledge_tree 部分"""
        tree_match = self.TREE_SECTION_PATTERN.search(content)
        if not tree_match:
            raise LLMParsingError("未找到 /basic_knowledge_tree 部分")

        tree_content = tree_match.group(1)
        nodes: list[ParsedNode] = []
        parent_stack: list[str] = []  # 按层级记录父节点

        for match in self.NODE_PATTERN.finditer(tree_content):
            asterisks = match.group(1)
            label = match.group(2).strip()
            score_str = match.group(3)

            level = len(asterisks)
            mastery = self._convert_mastery(float(score_str))

            # 确定父节点
            parent_label = None
            if level > 1 and len(parent_stack) >= level - 1:
                parent_label = parent_stack[level - 2]

            # 更新父节点栈
            # 清除当前层级及以下的节点
            while len(parent_stack) >= level:
                parent_stack.pop()
            parent_stack.append(label)

            nodes.append(
                ParsedNode(
                    label=label,
                    mastery=mastery,
                    level=level,
                    parent_label=parent_label,
                )
            )

        return nodes

    def _inject_root_node(
        self,
        nodes: list[ParsedNode],
        root_label: str,
    ) -> list[ParsedNode]:
        """
        注入虚拟根节点

        Args:
            nodes: 解析出的节点列表
            root_label: 根节点名称

        Returns:
            包含根节点的新节点列表
        """
        # 1. 创建根节点 (level=0, mastery=None 表示未知)
        root_node = ParsedNode(
            label=root_label,
            mastery=None,
            level=0,
            parent_label=None,
        )

        # 2. 创建新节点列表 (不变异原节点)
        # 将所有节点的 level +1，并将原一级节点的 parent 指向根节点
        updated_nodes = [
            ParsedNode(
                label=node.label,
                mastery=node.mastery,
                level=node.level + 1,
                parent_label=root_label if node.level == 1 else node.parent_label,
            )
            for node in nodes
        ]

        # 3. 返回新列表（根节点在最前面）
        return [root_node] + updated_nodes

    def _convert_mastery(self, score: float) -> int | None:
        """
        转换掌握分数

        Args:
            score: 原始分数 (-1, 0-1)

        Returns:
            转换后的分数 (None 或 0-100)
        """
        if score < 0:
            return None  # -1 表示未知
        # 0-1 范围转换为 0-100
        return min(100, max(0, int(score * 100)))

    def _build_tree_edges(self, nodes: list[ParsedNode]) -> list[ParsedEdge]:
        """根据父子关系构建树形边"""
        edges: list[ParsedEdge] = []

        for node in nodes:
            if node.parent_label:
                edges.append(
                    ParsedEdge(
                        source_label=node.parent_label,
                        target_label=node.label,
                        edge_type="knowledge_tree",
                    )
                )

        return edges

    def _parse_connections_section(
        self,
        content: str,
        nodes: list[ParsedNode],
    ) -> list[ParsedEdge]:
        """解析 /advanced_knowledge_connections 部分"""
        conn_match = self.CONNECTIONS_SECTION_PATTERN.search(content)
        if not conn_match:
            logger.debug("LLM 输出中未找到 /advanced_knowledge_connections 部分")
            return []  # 高级连接部分是可选的

        conn_content = conn_match.group(1)
        logger.debug("解析 advanced_knowledge_connections:\n%s", conn_content.strip())

        node_labels = {n.label for n in nodes}
        edges: list[ParsedEdge] = []
        skipped_edges: list[tuple[str, str, str]] = []

        for match in self.EDGE_PATTERN.finditer(conn_content):
            source = match.group(1).strip()
            target = match.group(2).strip()

            # 验证节点是否存在
            source_exists = source in node_labels
            target_exists = target in node_labels

            if source_exists and target_exists:
                edges.append(
                    ParsedEdge(
                        source_label=source,
                        target_label=target,
                        edge_type="advanced",
                    )
                )
            else:
                # 记录被跳过的边和原因
                missing = []
                if not source_exists:
                    missing.append(f"源节点 '{source}'")
                if not target_exists:
                    missing.append(f"目标节点 '{target}'")
                skipped_edges.append((source, target, " 和 ".join(missing)))

        # 汇总日志
        if skipped_edges:
            logger.warning(
                "跳过 %d 条无效的 advanced 边 (节点不存在于树中):",
                len(skipped_edges),
            )
            for source, target, reason in skipped_edges:
                logger.warning("  - %s -> %s (%s 不存在)", source, target, reason)

        logger.info(
            "解析 advanced 边完成: %d 条有效, %d 条跳过",
            len(edges),
            len(skipped_edges),
        )

        return edges

    # ===== 增量解析方法（用于流式生成场景） =====

    _INCR_NODE_RE = re.compile(r"^(\*+)\s*(.+?)\s*\[(-?\d+(?:\.\d+)?)\]\s*$")
    _INCR_EDGE_RE = re.compile(r"^(.+?)\s*->\s*(.+?)\s*$")

    @staticmethod
    def parse_incremental_node(line: str) -> dict | None:
        """
        尝试从单行解析节点: '** 概念名 [-1]'

        Returns:
            {"label": str, "level": int} 或 None
        """
        m = KnowledgeGraphParser._INCR_NODE_RE.match(line.strip())
        if m:
            return {"label": m.group(2).strip(), "level": len(m.group(1))}
        return None

    @staticmethod
    def parse_incremental_edge(line: str) -> dict | None:
        """
        尝试从单行解析边: '概念A->概念B'

        Returns:
            {"source": str, "target": str, "type": "advanced"} 或 None
        """
        m = KnowledgeGraphParser._INCR_EDGE_RE.match(line.strip())
        if m:
            src = m.group(1).strip()
            tgt = m.group(2).strip()
            # 排除明显不是边的行（如 section 标记）
            if src.startswith("/") or src.startswith("*"):
                return None
            return {"source": src, "target": tgt, "type": "advanced"}
        return None
