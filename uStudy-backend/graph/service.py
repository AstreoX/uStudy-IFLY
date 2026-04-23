"""Knowledge Graph Service - CRUD Operations"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import or_, select, delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Node, Edge, EdgeType, NodeUserMastery
from graph.exceptions import (
    NodeNotFoundError,
    EdgeNotFoundError,
    DuplicateNodeError,
    DuplicateEdgeError,
)

logger = logging.getLogger(__name__)


class GraphService:
    """Knowledge Graph Service for CRUD operations"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_graph(
        self,
        space_id: UUID,
        user_id: UUID | None = None,
        is_collaborative: bool = False,
    ) -> dict:
        """
        Get full graph overview for a learning space.

        Args:
            space_id: Learning space ID
            user_id: Current user ID (used in collaborative mode)
            is_collaborative: Whether this is a collaborative space

        Returns:
            dict with 'nodes' and 'edges' lists.
            In collaborative mode, per-user mastery is used and edges include user_id
            for learning_path edges.
        """
        if is_collaborative and user_id is not None:
            # Collaborative mode: LEFT JOIN node_user_mastery for per-user mastery
            stmt = (
                select(Node, NodeUserMastery.mastery.label("user_mastery"))
                .outerjoin(
                    NodeUserMastery,
                    (NodeUserMastery.node_id == Node.id)
                    & (NodeUserMastery.user_id == user_id),
                )
                .where(Node.space_id == space_id)
            )
            nodes_result = await self.db.execute(stmt)
            node_rows = nodes_result.all()

            nodes_data = [
                {
                    "id": str(row.Node.id),
                    "label": row.Node.label,
                    "mastery": row.user_mastery if row.user_mastery is not None else row.Node.mastery,
                }
                for row in node_rows
            ]

            # Edges: filter LEARNING_PATH to user-owned or legacy (NULL user_id)
            edges_result = await self.db.execute(
                select(Edge).where(
                    Edge.space_id == space_id,
                    or_(
                        Edge.type != EdgeType.LEARNING_PATH,
                        Edge.user_id == user_id,
                        Edge.user_id.is_(None),
                    ),
                )
            )
            edges = edges_result.scalars().all()

            edges_data = []
            for e in edges:
                edge_dict = {
                    "id": str(e.id),
                    "from_node_id": str(e.from_node_id),
                    "to_node_id": str(e.to_node_id),
                    "type": e.type.value,
                }
                if e.type == EdgeType.LEARNING_PATH:
                    edge_dict["user_id"] = str(e.user_id) if e.user_id else None
                edges_data.append(edge_dict)

            return {"nodes": nodes_data, "edges": edges_data}

        # Non-collaborative mode: existing behavior
        nodes_result = await self.db.execute(
            select(Node).where(Node.space_id == space_id)
        )
        nodes = nodes_result.scalars().all()

        edges_result = await self.db.execute(
            select(Edge).where(Edge.space_id == space_id)
        )
        edges = edges_result.scalars().all()

        return {
            "nodes": [
                {
                    "id": str(n.id),
                    "label": n.label,
                    "mastery": n.mastery,
                }
                for n in nodes
            ],
            "edges": [
                {
                    "id": str(e.id),
                    "from_node_id": str(e.from_node_id),
                    "to_node_id": str(e.to_node_id),
                    "type": e.type.value,
                }
                for e in edges
            ],
        }

    async def create_node(
        self,
        space_id: UUID,
        label: str,
        mastery: Optional[int] = None,
    ) -> Node:
        """
        Create a new knowledge node.

        Args:
            space_id: Learning space ID
            label: Node label/name (max 200 characters)
            mastery: Mastery score (0-100) or None for unknown

        Returns:
            Created Node object

        Raises:
            DuplicateNodeError: If node with same label exists in space
            ValueError: If label is empty or too long
        """
        # Validate label
        if not label or not label.strip():
            raise ValueError("节点名称不能为空")
        label = label.strip()
        if len(label) > 200:
            raise ValueError("节点名称过长（最多200字符）")

        node = Node(space_id=space_id, label=label, mastery=mastery)

        try:
            self.db.add(node)
            await self.db.commit()
            await self.db.refresh(node)
        except IntegrityError as e:
            await self.db.rollback()
            # Check if it's a duplicate key error from unique constraint
            error_msg = str(e.orig).lower() if e.orig else ""
            if "uq_nodes_space_label" in error_msg or "duplicate key" in error_msg:
                raise DuplicateNodeError(
                    f"Node '{label}' already exists in this space"
                )
            raise

        logger.info(f"Created node: {node.id} ({label}) in space {space_id}")
        return node

    async def delete_node(self, space_id: UUID, node_id: UUID) -> None:
        """
        Delete a node and all its related edges.

        Args:
            space_id: Learning space ID
            node_id: Node ID to delete

        Raises:
            NodeNotFoundError: If node not found
        """
        node = await self._get_node(space_id, node_id)

        # Delete related edges first (cascade should handle this, but explicit is better)
        await self.db.execute(
            delete(Edge).where(
                (Edge.from_node_id == node_id) | (Edge.to_node_id == node_id)
            )
        )

        await self.db.delete(node)
        await self.db.commit()

        logger.info(f"Deleted node: {node_id} from space {space_id}")

    async def create_edge(
        self,
        space_id: UUID,
        from_node_id: UUID,
        to_node_id: UUID,
        edge_type: str = "advanced",
    ) -> Edge:
        """
        Create a new edge between nodes.

        Args:
            space_id: Learning space ID
            from_node_id: Source node ID
            to_node_id: Target node ID
            edge_type: Edge type (knowledge_tree, learning_path, advanced)

        Returns:
            Created Edge object

        Raises:
            NodeNotFoundError: If either node not found
            DuplicateEdgeError: If edge already exists
        """
        # Validate nodes exist
        await self._get_node(space_id, from_node_id)
        await self._get_node(space_id, to_node_id)

        # Parse edge type
        try:
            edge_type_enum = EdgeType(edge_type)
        except ValueError:
            edge_type_enum = EdgeType.ADVANCED

        edge = Edge(
            space_id=space_id,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            type=edge_type_enum,
        )

        try:
            self.db.add(edge)
            await self.db.commit()
            await self.db.refresh(edge)
        except IntegrityError:
            await self.db.rollback()
            raise DuplicateEdgeError(
                f"Edge from {from_node_id} to {to_node_id} already exists"
            )

        logger.info(f"Created edge: {from_node_id} -> {to_node_id} ({edge_type})")
        return edge

    async def delete_edge(self, space_id: UUID, edge_id: UUID) -> None:
        """
        Delete an edge.

        Args:
            space_id: Learning space ID
            edge_id: Edge ID to delete

        Raises:
            EdgeNotFoundError: If edge not found
        """
        result = await self.db.execute(
            select(Edge).where(Edge.id == edge_id, Edge.space_id == space_id)
        )
        edge = result.scalar_one_or_none()

        if not edge:
            raise EdgeNotFoundError(f"Edge {edge_id} not found in space {space_id}")

        await self.db.delete(edge)
        await self.db.commit()

        logger.info(f"Deleted edge: {edge_id}")

    async def update_mastery(
        self,
        space_id: UUID,
        node_id: UUID,
        mastery: int,
        user_id: UUID | None = None,
        is_collaborative: bool = False,
    ) -> Node:
        """
        Update node mastery score.

        In collaborative mode, upserts into the per-user node_user_mastery table
        instead of modifying the shared Node.mastery column.

        Args:
            space_id: Learning space ID
            node_id: Node ID
            mastery: New mastery score (0-100)
            user_id: Current user ID (used in collaborative mode)
            is_collaborative: Whether this is a collaborative space

        Returns:
            Updated Node object (in collaborative mode, the Node.mastery is unchanged;
            the caller should use the passed mastery value for the user's view)

        Raises:
            NodeNotFoundError: If node not found
            ValueError: If mastery out of range
        """
        if mastery < 0 or mastery > 100:
            raise ValueError(f"Mastery must be between 0 and 100, got {mastery}")

        node = await self._get_node(space_id, node_id)

        if is_collaborative and user_id is not None:
            # Upsert per-user mastery in node_user_mastery table
            stmt = text("""
                INSERT INTO node_user_mastery (id, node_id, user_id, mastery, updated_at)
                VALUES (gen_random_uuid(), :node_id, :user_id, :mastery, NOW())
                ON CONFLICT (node_id, user_id)
                DO UPDATE SET mastery = :mastery, updated_at = NOW()
            """)
            await self.db.execute(
                stmt,
                {"node_id": node_id, "user_id": user_id, "mastery": mastery},
            )
            await self.db.commit()
            logger.info(
                f"Updated per-user mastery for node {node_id}, user {user_id}: {mastery}"
            )
            return node

        # Non-collaborative mode: update shared Node.mastery
        node.mastery = mastery
        await self.db.commit()
        await self.db.refresh(node)

        logger.info(f"Updated mastery for node {node_id}: {mastery}")
        return node

    async def get_children(
        self,
        space_id: UUID,
        node_id: UUID,
        max_depth: int = -1,
    ) -> list[dict]:
        """
        Get child nodes (nodes this node points to) with tree structure.

        Args:
            space_id: Learning space ID
            node_id: Parent node ID
            max_depth: Maximum depth to traverse (-1 for unlimited)

        Returns:
            List of child node dicts with nested children
        """
        # Validate node exists
        await self._get_node(space_id, node_id)

        return await self._get_children_recursive(
            space_id, node_id, max_depth, 0, visited=set()
        )

    async def _get_children_recursive(
        self,
        space_id: UUID,
        node_id: UUID,
        max_depth: int,
        current_depth: int,
        visited: set[UUID],
    ) -> list[dict]:
        """Recursively get children with depth limit and cycle detection."""
        # Cycle detection
        if node_id in visited:
            return []
        visited.add(node_id)

        if max_depth != -1 and current_depth >= max_depth:
            return []

        # Get edges from this node
        edges_result = await self.db.execute(
            select(Edge).where(
                Edge.space_id == space_id,
                Edge.from_node_id == node_id,
            )
        )
        edges = edges_result.scalars().all()

        if not edges:
            return []

        child_ids = [e.to_node_id for e in edges]

        # Get child nodes
        nodes_result = await self.db.execute(
            select(Node).where(Node.id.in_(child_ids))
        )
        children = nodes_result.scalars().all()

        result = []
        for child in children:
            child_dict = {
                "id": str(child.id),
                "label": child.label,
                "mastery": child.mastery,
                "children": await self._get_children_recursive(
                    space_id, child.id, max_depth, current_depth + 1, visited.copy()
                ),
            }
            result.append(child_dict)

        return result

    async def get_parents(self, space_id: UUID, node_id: UUID) -> list[dict]:
        """
        Get parent nodes (nodes pointing to this node).

        Args:
            space_id: Learning space ID
            node_id: Child node ID

        Returns:
            List of parent node dicts
        """
        # Validate node exists
        await self._get_node(space_id, node_id)

        # Get edges pointing to this node
        edges_result = await self.db.execute(
            select(Edge).where(
                Edge.space_id == space_id,
                Edge.to_node_id == node_id,
            )
        )
        edges = edges_result.scalars().all()

        if not edges:
            return []

        parent_ids = [e.from_node_id for e in edges]

        # Get parent nodes
        nodes_result = await self.db.execute(
            select(Node).where(Node.id.in_(parent_ids))
        )
        parents = nodes_result.scalars().all()

        return [
            {
                "id": str(p.id),
                "label": p.label,
                "mastery": p.mastery,
            }
            for p in parents
        ]

    async def get_siblings(self, space_id: UUID, node_id: UUID) -> list[dict]:
        """
        Get sibling nodes (nodes with same parent).

        Args:
            space_id: Learning space ID
            node_id: Node ID

        Returns:
            List of sibling node dicts (excluding the input node)
        """
        # Get parents first
        parents = await self.get_parents(space_id, node_id)

        if not parents:
            return []

        # Get all children of parents
        sibling_ids = set()
        for parent in parents:
            parent_id = UUID(parent["id"])
            # Get edges from parent
            edges_result = await self.db.execute(
                select(Edge).where(
                    Edge.space_id == space_id,
                    Edge.from_node_id == parent_id,
                )
            )
            edges = edges_result.scalars().all()

            for edge in edges:
                if edge.to_node_id != node_id:
                    sibling_ids.add(edge.to_node_id)

        if not sibling_ids:
            return []

        # Get sibling nodes
        nodes_result = await self.db.execute(
            select(Node).where(Node.id.in_(sibling_ids))
        )
        siblings = nodes_result.scalars().all()

        return [
            {
                "id": str(s.id),
                "label": s.label,
                "mastery": s.mastery,
            }
            for s in siblings
        ]

    async def create_learning_path(
        self,
        space_id: UUID,
        node_ids: list[UUID],
        user_id: UUID | None = None,
    ) -> list[Edge]:
        """
        Create a learning path by connecting nodes in sequence.

        Args:
            space_id: Learning space ID
            node_ids: List of node IDs in learning order
            user_id: Owner user ID for per-user learning paths (collaborative spaces)

        Returns:
            List of created Edge objects

        Raises:
            NodeNotFoundError: If any node not found
            ValueError: If less than 2 nodes provided
        """
        if len(node_ids) < 2:
            raise ValueError("Learning path requires at least 2 nodes")

        # Validate all nodes exist
        for nid in node_ids:
            await self._get_node(space_id, nid)

        # Create edges between consecutive nodes
        created_edges = []
        for i in range(len(node_ids) - 1):
            from_id = node_ids[i]
            to_id = node_ids[i + 1]

            # Check if edge already exists (match user_id for per-user paths)
            existing_query = select(Edge).where(
                Edge.space_id == space_id,
                Edge.from_node_id == from_id,
                Edge.to_node_id == to_id,
                Edge.type == EdgeType.LEARNING_PATH,
            )
            if user_id is not None:
                existing_query = existing_query.where(Edge.user_id == user_id)
            else:
                existing_query = existing_query.where(Edge.user_id.is_(None))

            existing = await self.db.execute(existing_query)
            if existing.scalar_one_or_none():
                continue  # Skip existing edges

            edge = Edge(
                space_id=space_id,
                from_node_id=from_id,
                to_node_id=to_id,
                type=EdgeType.LEARNING_PATH,
            )
            if user_id is not None:
                edge.user_id = user_id
            self.db.add(edge)
            created_edges.append(edge)

        await self.db.commit()

        # Refresh all created edges
        for edge in created_edges:
            await self.db.refresh(edge)

        logger.info(f"Created learning path with {len(created_edges)} edges")
        return created_edges

    async def _get_node(self, space_id: UUID, node_id: UUID) -> Node:
        """
        Get node with validation.

        Raises:
            NodeNotFoundError: If node not found or not in space
        """
        result = await self.db.execute(
            select(Node).where(Node.id == node_id, Node.space_id == space_id)
        )
        node = result.scalar_one_or_none()

        if not node:
            raise NodeNotFoundError(f"Node {node_id} not found in space {space_id}")

        return node

    async def get_node_by_label(
        self, space_id: UUID, label: str
    ) -> Optional[Node]:
        """
        Get node by label.

        Args:
            space_id: Learning space ID
            label: Node label/name

        Returns:
            Node object if found, None otherwise.
            If multiple nodes exist with the same label, returns the first one
            (ordered by id for consistency) and logs a warning.
        """
        result = await self.db.execute(
            select(Node)
            .where(Node.space_id == space_id, Node.label == label)
            .order_by(Node.id)
            .limit(2)
        )
        nodes = result.scalars().all()

        if not nodes:
            return None

        if len(nodes) > 1:
            # Sanitize label for logging (防止日志注入)
            safe_label = label[:50].replace("\n", " ").replace("\r", "")
            node_ids = [str(n.id) for n in nodes]
            logger.warning(
                f"Duplicate nodes found for label '{safe_label}' in space {space_id}. "
                f"Node IDs: {node_ids}. Using node {nodes[0].id}."
            )

        return nodes[0]

    async def get_edge_by_nodes(
        self,
        space_id: UUID,
        from_node_id: UUID,
        to_node_id: UUID,
    ) -> Optional[Edge]:
        """
        Get edge by source and target node IDs.

        Args:
            space_id: Learning space ID
            from_node_id: Source node ID
            to_node_id: Target node ID

        Returns:
            Edge object if found, None otherwise
        """
        result = await self.db.execute(
            select(Edge).where(
                Edge.space_id == space_id,
                Edge.from_node_id == from_node_id,
                Edge.to_node_id == to_node_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_all_learning_paths(
        self,
        space_id: UUID,
        user_id: UUID | None = None,
    ) -> int:
        """
        Delete learning_path edges in a space.

        When user_id is provided, only deletes LEARNING_PATH edges owned by that user.
        When user_id is None, deletes all LEARNING_PATH edges in the space (legacy behavior).

        Args:
            space_id: Learning space ID
            user_id: If provided, only delete this user's learning path edges

        Returns:
            Number of deleted edges

        Raises:
            Exception: If database operation fails
        """
        try:
            delete_stmt = delete(Edge).where(
                Edge.space_id == space_id,
                Edge.type == EdgeType.LEARNING_PATH,
            )
            if user_id is not None:
                delete_stmt = delete_stmt.where(Edge.user_id == user_id)

            result = await self.db.execute(delete_stmt)
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete learning paths in space {space_id}: {e}")
            raise

        deleted_count = result.rowcount
        logger.info(f"Deleted {deleted_count} learning path edges in space {space_id}")
        return deleted_count

    async def get_postorder_traversal(
        self,
        space_id: UUID,
        node_id: UUID,
    ) -> list[str]:
        """
        对以指定节点为根的知识树子树进行后序遍历。

        只使用 knowledge_tree 类型的边构建子树。
        后序遍历：先访问所有子节点，最后访问根节点。

        Args:
            space_id: 学习空间 ID
            node_id: 根节点 ID

        Returns:
            按后序遍历顺序排列的节点名称列表

        Raises:
            NodeNotFoundError: 节点不存在
        """
        # 验证根节点存在
        root_node = await self._get_node(space_id, node_id)

        # 只获取 knowledge_tree 类型的边
        edges_result = await self.db.execute(
            select(Edge).where(
                Edge.space_id == space_id,
                Edge.type == EdgeType.KNOWLEDGE_TREE,
            )
        )
        edges = edges_result.scalars().all()

        # 构建邻接表（父节点 -> 子节点列表）
        children_map: dict[UUID, list[UUID]] = {}
        for edge in edges:
            children_map.setdefault(edge.from_node_id, []).append(edge.to_node_id)

        # 获取所有节点用于标签查找
        nodes_result = await self.db.execute(
            select(Node).where(Node.space_id == space_id)
        )
        all_nodes = nodes_result.scalars().all()
        node_label_map = {n.id: n.label for n in all_nodes}

        # 后序遍历（带循环检测）
        result: list[str] = []
        visited: set[UUID] = set()

        def dfs_postorder(current_id: UUID) -> None:
            if current_id in visited:
                return  # 检测到循环，跳过
            visited.add(current_id)

            # 先访问所有子节点（后序）
            for child_id in children_map.get(current_id, []):
                dfs_postorder(child_id)

            # 最后添加当前节点
            label = node_label_map.get(current_id)
            if label:
                result.append(label)

        dfs_postorder(node_id)

        return result
