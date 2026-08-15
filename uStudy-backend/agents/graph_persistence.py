"""知识图谱持久化共享工具函数"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from agents.parsers.knowledge_graph import ParsedKnowledgeGraph
from db.models import Edge, EdgeType, Node

logger = logging.getLogger(__name__)


def map_edge_type(edge_type_str: str) -> EdgeType:
    """映射边类型字符串到枚举"""
    if edge_type_str == "knowledge_tree":
        return EdgeType.KNOWLEDGE_TREE
    elif edge_type_str == "advanced":
        return EdgeType.ADVANCED
    else:
        # 默认使用 KNOWLEDGE_TREE
        return EdgeType.KNOWLEDGE_TREE


async def persist_graph(
    db: AsyncSession,
    space_id: UUID,
    parsed_graph: ParsedKnowledgeGraph,
) -> tuple[int, int]:
    """
    将解析后的图谱持久化到数据库

    Args:
        db: 数据库会话
        space_id: 学习空间 ID
        parsed_graph: 解析后的知识图谱

    Returns:
        (node_count, edge_count)
    """
    label_to_id: dict[str, UUID] = {}

    # 1. 创建所有节点（跳过重复的 label）
    for parsed_node in parsed_graph.nodes:
        if parsed_node.label in label_to_id:
            logger.debug("跳过重复节点: %s", parsed_node.label)
            continue

        node = Node(
            space_id=space_id,
            label=parsed_node.label,
            mastery=parsed_node.mastery,
        )
        db.add(node)
        await db.flush()
        label_to_id[parsed_node.label] = node.id

    # 2. 创建所有边
    edge_count = 0
    for parsed_edge in parsed_graph.edges:
        source_id = label_to_id.get(parsed_edge.source_label)
        target_id = label_to_id.get(parsed_edge.target_label)

        if source_id and target_id:
            edge_type = map_edge_type(parsed_edge.edge_type)
            edge = Edge(
                space_id=space_id,
                from_node_id=source_id,
                to_node_id=target_id,
                type=edge_type,
            )
            db.add(edge)
            edge_count += 1

    await db.commit()
    return len(label_to_id), edge_count
