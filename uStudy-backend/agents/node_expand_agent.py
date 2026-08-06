"""节点扩展 Agent"""

import logging
import re
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.exceptions import (
    LLMClientError,
    LLMParsingError,
    LLMParsingErrorWithOutput,
)
from agents.llm.client import OpenRouterClient
from agents.llm.prompts import build_node_expand_prompt
from db.models import Edge, EdgeType, Node
from graph.service import GraphService

logger = logging.getLogger(__name__)


def _parse_expand_result(llm_output: str) -> list[str]:
    """
    从 LLM 输出中解析 <expand_result> 标签内的子节点标签列表。

    格式示例：
      <expand_result>
      * 子节点名称 [-1]
      </expand_result>

    Returns:
        子节点名称列表（已去空白），若解析失败则返回空列表
    """
    match = re.search(r"<expand_result>(.*?)</expand_result>", llm_output, re.DOTALL)
    if not match:
        return []

    block = match.group(1)
    labels = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("*"):
            continue
        # 移除前缀 "* " 和后缀 " [-1]" 等评分标注
        label = line.lstrip("* ").strip()
        label = re.sub(r"\s*\[-?\d*\.?\d*\]\s*$", "", label).strip()
        if label:
            labels.append(label)

    return labels


class NodeExpandAgent:
    """节点扩展 Agent：为指定节点生成 3-5 个子节点"""

    MAX_RETRIES = 3

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm_client = OpenRouterClient()

    async def expand(
        self,
        user_id: UUID,
        space_id: UUID,
        node_id: UUID,
    ) -> tuple[int, int]:
        """
        为指定节点生成子节点并持久化

        Args:
            user_id: 用户 ID（未直接使用，由 service 层验证权限）
            space_id: 学习空间 ID
            node_id: 目标节点 ID

        Returns:
            (node_count, edge_count) 新增的节点和边数量

        Raises:
            LLMClientError: LLM 调用失败
            LLMParsingError: 输出解析失败
        """
        # 1. 获取目标节点信息
        node = await self._get_node(space_id, node_id)

        # 2. 获取已有子节点（避免重复）
        existing_children = await self._get_direct_children(space_id, node_id)
        existing_labels = [c.label for c in existing_children]

        # 3. 获取父节点（用于 prompt 上下文）
        parent_label = await self._get_parent_label(space_id, node_id)

        # 3.5 获取完整知识图谱结构（供 LLM 参考避免重复）
        # 延迟导入避免循环依赖: agents → chat.tools → agents
        from chat.tools.graph_tools import build_knowledge_tree_text

        graph_service = GraphService(self.db)
        graph_data = await graph_service.get_graph(space_id)
        knowledge_tree_text = build_knowledge_tree_text(graph_data["nodes"], graph_data["edges"])

        # 4. 调用 LLM 生成子节点（带重试）
        new_labels = await self._call_llm_with_retry(
            node_label=node.label,
            parent_label=parent_label,
            existing_children=existing_labels,
            knowledge_tree_text=knowledge_tree_text,
        )

        if not new_labels:
            raise LLMParsingError("LLM 未生成任何有效子节点")

        # 5. 去重（过滤已有子节点 + 自身名称）
        existing_set = {lbl.strip().lower() for lbl in existing_labels}
        existing_set.add(node.label.strip().lower())
        unique_labels = []
        seen = set()
        for lbl in new_labels:
            key = lbl.strip().lower()
            if key not in existing_set and key not in seen:
                unique_labels.append(lbl)
                seen.add(key)

        if not unique_labels:
            raise LLMParsingError("生成的子节点全部与已有节点重复")

        # 6. 创建新节点 + 知识树边
        node_count, edge_count = await self._persist_children(
            space_id=space_id,
            parent_node_id=node_id,
            child_labels=unique_labels,
        )

        logger.info(
            "节点扩展完成: node_id=%s, label=%s, new_nodes=%d, new_edges=%d",
            node_id,
            node.label,
            node_count,
            edge_count,
        )
        return node_count, edge_count

    async def _get_node(self, space_id: UUID, node_id: UUID) -> Node:
        result = await self.db.execute(
            select(Node).where(Node.id == node_id, Node.space_id == space_id)
        )
        node = result.scalar_one_or_none()
        if not node:
            raise ValueError(f"节点不存在: {node_id}")
        return node

    async def _get_direct_children(self, space_id: UUID, node_id: UUID) -> list[Node]:
        """获取直接子节点（通过 knowledge_tree 边）"""
        edges_result = await self.db.execute(
            select(Edge).where(
                Edge.space_id == space_id,
                Edge.from_node_id == node_id,
                Edge.type == EdgeType.KNOWLEDGE_TREE,
            )
        )
        edges = edges_result.scalars().all()
        if not edges:
            return []

        child_ids = [e.to_node_id for e in edges]
        nodes_result = await self.db.execute(
            select(Node).where(Node.id.in_(child_ids))
        )
        return list(nodes_result.scalars().all())

    async def _get_parent_label(self, space_id: UUID, node_id: UUID) -> str | None:
        """获取父节点名称（通过 knowledge_tree 边）"""
        edge_result = await self.db.execute(
            select(Edge).where(
                Edge.space_id == space_id,
                Edge.to_node_id == node_id,
                Edge.type == EdgeType.KNOWLEDGE_TREE,
            ).limit(1)
        )
        edge = edge_result.scalar_one_or_none()
        if not edge:
            return None

        parent_result = await self.db.execute(
            select(Node).where(Node.id == edge.from_node_id)
        )
        parent = parent_result.scalar_one_or_none()
        return parent.label if parent else None

    async def _call_llm_with_retry(
        self,
        node_label: str,
        parent_label: str | None,
        existing_children: list[str],
        knowledge_tree_text: str = "",
    ) -> list[str]:
        """调用 LLM 并重试，返回解析出的子节点名称列表"""
        messages = build_node_expand_prompt(
            node_label=node_label,
            parent_label=parent_label,
            existing_children=existing_children,
            knowledge_tree_text=knowledge_tree_text,
        )

        last_error: Exception | None = None
        last_output: str | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info("节点扩展 LLM 调用尝试 %d/%d", attempt + 1, self.MAX_RETRIES)
                llm_output = await self.llm_client.complete(messages)
                last_output = llm_output

                labels = _parse_expand_result(llm_output)
                if labels:
                    return labels

                last_error = LLMParsingError("未找到 <expand_result> 标签或无有效子节点")
                logger.warning(
                    "解析失败 (尝试 %d/%d): %s", attempt + 1, self.MAX_RETRIES, last_error
                )

            except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
                logger.warning("LLM 调用失败 (尝试 %d/%d): %s", attempt + 1, self.MAX_RETRIES, e)
                last_error = LLMClientError(str(e))

        if last_output and isinstance(last_error, LLMParsingError):
            raise LLMParsingErrorWithOutput(str(last_error), llm_output=last_output)
        raise last_error or LLMClientError("LLM 调用失败")

    async def _persist_children(
        self,
        space_id: UUID,
        parent_node_id: UUID,
        child_labels: list[str],
    ) -> tuple[int, int]:
        """创建子节点和知识树边，返回 (node_count, edge_count)。

        对于 space 中已存在同名节点的情况，复用已有节点只创建 edge。
        """
        node_count = 0
        edge_count = 0

        for label in child_labels:
            # 查询 space 中是否已有同名节点（不区分大小写）
            existing = await self.db.execute(
                select(Node).where(
                    Node.space_id == space_id,
                    func.lower(Node.label) == label.strip().lower(),
                )
            )
            existing_node = existing.scalar_one_or_none()

            if existing_node:
                target_node = existing_node
            else:
                target_node = Node(space_id=space_id, label=label, mastery=None)
                self.db.add(target_node)
                await self.db.flush()
                node_count += 1

            # 检查 edge 是否已存在
            existing_edge = await self.db.execute(
                select(Edge).where(
                    Edge.space_id == space_id,
                    Edge.from_node_id == parent_node_id,
                    Edge.to_node_id == target_node.id,
                    Edge.type == EdgeType.KNOWLEDGE_TREE,
                )
            )
            if not existing_edge.scalar_one_or_none():
                edge = Edge(
                    space_id=space_id,
                    from_node_id=parent_node_id,
                    to_node_id=target_node.id,
                    type=EdgeType.KNOWLEDGE_TREE,
                )
                self.db.add(edge)
                edge_count += 1

        await self.db.commit()
        return node_count, edge_count
