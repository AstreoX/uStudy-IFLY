"""GraphService 单元测试"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Space, Node, Edge, EdgeType
from graph.service import GraphService
from graph.exceptions import (
    NodeNotFoundError,
    EdgeNotFoundError,
    DuplicateNodeError,
    DuplicateEdgeError,
)


class TestGraphServiceNode:
    """节点 CRUD 操作测试"""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> GraphService:
        """创建 GraphService 实例"""
        return GraphService(db_session)

    # ==================== 创建节点测试 ====================

    @pytest.mark.asyncio
    async def test_create_node_success(
        self, service: GraphService, graph_test_space: Space
    ):
        """正常创建节点"""
        node = await service.create_node(
            space_id=graph_test_space.id,
            label="测试节点",
            mastery=50,
        )

        assert node is not None
        assert node.label == "测试节点"
        assert node.mastery == 50
        assert node.space_id == graph_test_space.id

    @pytest.mark.asyncio
    async def test_create_node_without_mastery(
        self, service: GraphService, graph_test_space: Space
    ):
        """创建无掌握分的节点"""
        node = await service.create_node(
            space_id=graph_test_space.id,
            label="未学习节点",
            mastery=None,
        )

        assert node.mastery is None

    @pytest.mark.asyncio
    async def test_create_node_with_mastery_zero(
        self, service: GraphService, graph_test_space: Space
    ):
        """创建掌握分为0的节点"""
        node = await service.create_node(
            space_id=graph_test_space.id,
            label="零掌握分节点",
            mastery=0,
        )

        assert node.mastery == 0

    @pytest.mark.asyncio
    async def test_create_node_with_mastery_100(
        self, service: GraphService, graph_test_space: Space
    ):
        """创建掌握分为100的节点"""
        node = await service.create_node(
            space_id=graph_test_space.id,
            label="满分节点",
            mastery=100,
        )

        assert node.mastery == 100

    @pytest.mark.asyncio
    async def test_create_node_empty_label_raises(
        self, service: GraphService, graph_test_space: Space
    ):
        """空标签应抛出 ValueError"""
        with pytest.raises(ValueError, match="节点名称不能为空"):
            await service.create_node(
                space_id=graph_test_space.id,
                label="",
            )

    @pytest.mark.asyncio
    async def test_create_node_whitespace_only_label_raises(
        self, service: GraphService, graph_test_space: Space
    ):
        """纯空白标签应抛出 ValueError"""
        with pytest.raises(ValueError, match="节点名称不能为空"):
            await service.create_node(
                space_id=graph_test_space.id,
                label="   ",
            )

    @pytest.mark.asyncio
    async def test_create_node_label_max_length(
        self, service: GraphService, graph_test_space: Space
    ):
        """标签超过200字符应报错"""
        long_label = "x" * 201
        with pytest.raises(ValueError, match="节点名称过长"):
            await service.create_node(
                space_id=graph_test_space.id,
                label=long_label,
            )

    @pytest.mark.asyncio
    async def test_create_node_label_exactly_200_chars(
        self, service: GraphService, graph_test_space: Space
    ):
        """标签正好200字符应成功"""
        label_200 = "x" * 200
        node = await service.create_node(
            space_id=graph_test_space.id,
            label=label_200,
        )
        assert len(node.label) == 200

    @pytest.mark.asyncio
    async def test_create_node_duplicate_label_raises(
        self, service: GraphService, graph_test_space: Space
    ):
        """创建重复标签节点应抛出 DuplicateNodeError"""
        await service.create_node(
            space_id=graph_test_space.id,
            label="唯一节点",
        )

        with pytest.raises(DuplicateNodeError):
            await service.create_node(
                space_id=graph_test_space.id,
                label="唯一节点",
            )

    @pytest.mark.asyncio
    async def test_create_node_same_label_different_space(
        self, service: GraphService, db_session: AsyncSession, graph_test_user
    ):
        """不同空间可以有相同标签的节点"""
        space1 = Space(id=uuid4(), user_id=graph_test_user.id, name="Space1", color="#111")
        space2 = Space(id=uuid4(), user_id=graph_test_user.id, name="Space2", color="#222")
        db_session.add(space1)
        db_session.add(space2)
        await db_session.commit()

        node1 = await service.create_node(space_id=space1.id, label="共同节点")
        node2 = await service.create_node(space_id=space2.id, label="共同节点")

        assert node1.id != node2.id
        assert node1.space_id != node2.space_id

    @pytest.mark.asyncio
    async def test_create_node_strips_whitespace(
        self, service: GraphService, graph_test_space: Space
    ):
        """标签前后空白应被去除"""
        node = await service.create_node(
            space_id=graph_test_space.id,
            label="  带空白的标签  ",
        )
        assert node.label == "带空白的标签"

    # ==================== create_node_with_edge 测试 ====================

    @pytest.mark.asyncio
    async def test_create_node_with_edge_success(
        self, service: GraphService, graph_test_space: Space
    ):
        """原子创建节点 + 边"""
        parent = await service.create_node(graph_test_space.id, "父节点")
        node, edge = await service.create_node_with_edge(
            space_id=graph_test_space.id,
            label="子节点",
            from_node_id=parent.id,
            mastery=75,
        )

        assert node.label == "子节点"
        assert node.mastery == 75
        assert edge.from_node_id == parent.id
        assert edge.to_node_id == node.id
        assert edge.type == EdgeType.KNOWLEDGE_TREE

    @pytest.mark.asyncio
    async def test_create_node_with_edge_from_node_not_found(
        self, service: GraphService, graph_test_space: Space
    ):
        """from_node 不存在应抛 NodeNotFoundError"""
        fake_id = uuid4()
        with pytest.raises(NodeNotFoundError):
            await service.create_node_with_edge(
                space_id=graph_test_space.id,
                label="子节点",
                from_node_id=fake_id,
            )

    @pytest.mark.asyncio
    async def test_create_node_with_edge_duplicate_label(
        self, service: GraphService, graph_test_space: Space
    ):
        """重复节点名应抛 DuplicateNodeError"""
        parent = await service.create_node(graph_test_space.id, "根")
        await service.create_node_with_edge(
            graph_test_space.id, "子", parent.id,
        )
        with pytest.raises(DuplicateNodeError):
            await service.create_node_with_edge(
                graph_test_space.id, "子", parent.id,
            )

    # ==================== 删除节点测试 ====================

    @pytest.mark.asyncio
    async def test_delete_node_success(
        self, service: GraphService, sample_graph: dict
    ):
        """正常删除节点"""
        space = sample_graph["space"]
        array_node = sample_graph["nodes"]["array"]

        await service.delete_node(space.id, array_node.id)

        # 验证节点已删除
        with pytest.raises(NodeNotFoundError):
            await service._get_node(space.id, array_node.id)

    @pytest.mark.asyncio
    async def test_delete_node_cascade_edges(
        self, service: GraphService, sample_graph: dict, db_session: AsyncSession
    ):
        """删除节点应同时删除关联边"""
        space = sample_graph["space"]
        linear_node = sample_graph["nodes"]["linear"]

        # linear 节点有多条边：root->linear, linear->array, linear->linked_list
        await service.delete_node(space.id, linear_node.id)

        # 验证相关边已删除
        graph = await service.get_graph(space.id)
        edge_ids = [
            (e["from_node_id"], e["to_node_id"])
            for e in graph["edges"]
        ]
        linear_id_str = str(linear_node.id)
        assert not any(
            linear_id_str in (from_id, to_id)
            for from_id, to_id in edge_ids
        )

    @pytest.mark.asyncio
    async def test_delete_node_not_found(
        self, service: GraphService, graph_test_space: Space
    ):
        """删除不存在的节点应抛出 NodeNotFoundError"""
        fake_id = uuid4()
        with pytest.raises(NodeNotFoundError):
            await service.delete_node(graph_test_space.id, fake_id)


class TestGraphServiceEdge:
    """边 CRUD 操作测试"""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> GraphService:
        return GraphService(db_session)

    # ==================== 创建边测试 ====================

    @pytest.mark.asyncio
    async def test_create_edge_success(
        self, service: GraphService, graph_test_space: Space
    ):
        """正常创建边"""
        node1 = await service.create_node(graph_test_space.id, "节点1")
        node2 = await service.create_node(graph_test_space.id, "节点2")

        edge = await service.create_edge(
            space_id=graph_test_space.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            edge_type="advanced",
        )

        assert edge is not None
        assert edge.from_node_id == node1.id
        assert edge.to_node_id == node2.id
        assert edge.type == EdgeType.ADVANCED

    @pytest.mark.asyncio
    async def test_create_edge_all_types(
        self, service: GraphService, graph_test_space: Space
    ):
        """测试三种边类型"""
        node1 = await service.create_node(graph_test_space.id, "N1")
        node2 = await service.create_node(graph_test_space.id, "N2")
        node3 = await service.create_node(graph_test_space.id, "N3")
        node4 = await service.create_node(graph_test_space.id, "N4")

        edge_tree = await service.create_edge(
            graph_test_space.id, node1.id, node2.id, "knowledge_tree"
        )
        edge_path = await service.create_edge(
            graph_test_space.id, node2.id, node3.id, "learning_path"
        )
        edge_adv = await service.create_edge(
            graph_test_space.id, node3.id, node4.id, "advanced"
        )

        assert edge_tree.type == EdgeType.KNOWLEDGE_TREE
        assert edge_path.type == EdgeType.LEARNING_PATH
        assert edge_adv.type == EdgeType.ADVANCED

    @pytest.mark.asyncio
    async def test_create_edge_invalid_type_defaults_to_advanced(
        self, service: GraphService, graph_test_space: Space
    ):
        """无效边类型默认为 advanced"""
        node1 = await service.create_node(graph_test_space.id, "N1")
        node2 = await service.create_node(graph_test_space.id, "N2")

        edge = await service.create_edge(
            graph_test_space.id, node1.id, node2.id, "invalid_type"
        )
        assert edge.type == EdgeType.ADVANCED

    @pytest.mark.asyncio
    async def test_create_edge_node_not_found(
        self, service: GraphService, graph_test_space: Space
    ):
        """节点不存在时创建边应抛出 NodeNotFoundError"""
        node1 = await service.create_node(graph_test_space.id, "存在的节点")
        fake_id = uuid4()

        with pytest.raises(NodeNotFoundError):
            await service.create_edge(
                graph_test_space.id, node1.id, fake_id
            )

    @pytest.mark.asyncio
    async def test_create_edge_duplicate_raises(
        self, service: GraphService, graph_test_space: Space
    ):
        """创建重复边应抛出 DuplicateEdgeError"""
        node1 = await service.create_node(graph_test_space.id, "A")
        node2 = await service.create_node(graph_test_space.id, "B")

        await service.create_edge(graph_test_space.id, node1.id, node2.id)

        with pytest.raises(DuplicateEdgeError):
            await service.create_edge(graph_test_space.id, node1.id, node2.id)

    # ==================== 删除边测试 ====================

    @pytest.mark.asyncio
    async def test_delete_edge_success(
        self, service: GraphService, sample_graph: dict
    ):
        """正常删除边"""
        space = sample_graph["space"]
        edge = sample_graph["edges"][0]

        await service.delete_edge(space.id, edge.id)

        with pytest.raises(EdgeNotFoundError):
            await service.delete_edge(space.id, edge.id)

    @pytest.mark.asyncio
    async def test_delete_edge_not_found(
        self, service: GraphService, graph_test_space: Space
    ):
        """删除不存在的边应抛出 EdgeNotFoundError"""
        fake_id = uuid4()
        with pytest.raises(EdgeNotFoundError):
            await service.delete_edge(graph_test_space.id, fake_id)


class TestGraphServiceQuery:
    """图谱查询测试"""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> GraphService:
        return GraphService(db_session)

    # ==================== 获取图谱概览测试 ====================

    @pytest.mark.asyncio
    async def test_get_graph_empty(
        self, service: GraphService, empty_graph_space: Space
    ):
        """空图谱概览"""
        graph = await service.get_graph(empty_graph_space.id)

        assert graph["nodes"] == []
        assert graph["edges"] == []

    @pytest.mark.asyncio
    async def test_get_graph_with_data(
        self, service: GraphService, sample_graph: dict
    ):
        """有数据的图谱概览"""
        space = sample_graph["space"]
        graph = await service.get_graph(space.id)

        assert len(graph["nodes"]) == 7
        assert len(graph["edges"]) == 6

        # 验证节点格式
        node = graph["nodes"][0]
        assert "id" in node
        assert "label" in node
        assert "mastery" in node

        # 验证边格式
        edge = graph["edges"][0]
        assert "id" in edge
        assert "from_node_id" in edge
        assert "to_node_id" in edge
        assert "type" in edge

    # ==================== 子节点查询测试 ====================

    @pytest.mark.asyncio
    async def test_get_children_direct(
        self, service: GraphService, sample_graph: dict
    ):
        """获取直接子节点"""
        space = sample_graph["space"]
        root = sample_graph["nodes"]["root"]

        children = await service.get_children(space.id, root.id, max_depth=1)

        assert len(children) == 2
        labels = [c["label"] for c in children]
        assert "线性结构" in labels
        assert "非线性结构" in labels

    @pytest.mark.asyncio
    async def test_get_children_recursive(
        self, service: GraphService, sample_graph: dict
    ):
        """递归获取所有子节点"""
        space = sample_graph["space"]
        root = sample_graph["nodes"]["root"]

        children = await service.get_children(space.id, root.id, max_depth=-1)

        # 递归结构验证
        assert len(children) == 2
        linear = next(c for c in children if c["label"] == "线性结构")
        assert len(linear["children"]) == 2  # 数组, 链表

    @pytest.mark.asyncio
    async def test_get_children_max_depth(
        self, service: GraphService, sample_graph: dict
    ):
        """限制最大深度"""
        space = sample_graph["space"]
        root = sample_graph["nodes"]["root"]

        children = await service.get_children(space.id, root.id, max_depth=1)

        # 深度1只返回直接子节点
        for child in children:
            assert child["children"] == []

    @pytest.mark.asyncio
    async def test_get_children_empty(
        self, service: GraphService, sample_graph: dict
    ):
        """无子节点返回空列表"""
        space = sample_graph["space"]
        array = sample_graph["nodes"]["array"]

        children = await service.get_children(space.id, array.id)
        assert children == []

    @pytest.mark.asyncio
    async def test_get_children_circular_reference(
        self, service: GraphService, circular_graph: dict
    ):
        """循环引用不死循环"""
        space = circular_graph["space"]
        node_a = circular_graph["nodes"]["a"]

        # 不应该无限循环
        children = await service.get_children(space.id, node_a.id, max_depth=-1)

        # 应该正常返回
        assert isinstance(children, list)

    @pytest.mark.asyncio
    async def test_get_children_node_not_found(
        self, service: GraphService, graph_test_space: Space
    ):
        """节点不存在时应抛出 NodeNotFoundError"""
        fake_id = uuid4()
        with pytest.raises(NodeNotFoundError):
            await service.get_children(graph_test_space.id, fake_id)

    # ==================== 父节点查询测试 ====================

    @pytest.mark.asyncio
    async def test_get_parents_success(
        self, service: GraphService, sample_graph: dict
    ):
        """获取父节点"""
        space = sample_graph["space"]
        array = sample_graph["nodes"]["array"]

        parents = await service.get_parents(space.id, array.id)

        assert len(parents) == 1
        assert parents[0]["label"] == "线性结构"

    @pytest.mark.asyncio
    async def test_get_parents_root_node(
        self, service: GraphService, sample_graph: dict
    ):
        """根节点无父节点"""
        space = sample_graph["space"]
        root = sample_graph["nodes"]["root"]

        parents = await service.get_parents(space.id, root.id)
        assert parents == []

    @pytest.mark.asyncio
    async def test_get_parents_multiple(
        self, service: GraphService, graph_test_space: Space
    ):
        """多个父节点"""
        node1 = await service.create_node(graph_test_space.id, "父1")
        node2 = await service.create_node(graph_test_space.id, "父2")
        child = await service.create_node(graph_test_space.id, "子")

        await service.create_edge(graph_test_space.id, node1.id, child.id)
        await service.create_edge(graph_test_space.id, node2.id, child.id)

        parents = await service.get_parents(graph_test_space.id, child.id)

        assert len(parents) == 2
        labels = [p["label"] for p in parents]
        assert "父1" in labels
        assert "父2" in labels

    # ==================== 兄弟节点查询测试 ====================

    @pytest.mark.asyncio
    async def test_get_siblings_success(
        self, service: GraphService, sample_graph: dict
    ):
        """获取兄弟节点"""
        space = sample_graph["space"]
        array = sample_graph["nodes"]["array"]

        siblings = await service.get_siblings(space.id, array.id)

        assert len(siblings) == 1
        assert siblings[0]["label"] == "链表"

    @pytest.mark.asyncio
    async def test_get_siblings_no_parent(
        self, service: GraphService, sample_graph: dict
    ):
        """无父节点时无兄弟"""
        space = sample_graph["space"]
        root = sample_graph["nodes"]["root"]

        siblings = await service.get_siblings(space.id, root.id)
        assert siblings == []

    @pytest.mark.asyncio
    async def test_get_siblings_only_child(
        self, service: GraphService, graph_test_space: Space
    ):
        """独生子返回空"""
        parent = await service.create_node(graph_test_space.id, "父")
        only_child = await service.create_node(graph_test_space.id, "独生子")
        await service.create_edge(graph_test_space.id, parent.id, only_child.id)

        siblings = await service.get_siblings(graph_test_space.id, only_child.id)
        assert siblings == []


class TestGraphServiceMastery:
    """掌握分操作测试"""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> GraphService:
        return GraphService(db_session)

    @pytest.mark.asyncio
    async def test_update_mastery_success(
        self, service: GraphService, sample_graph: dict
    ):
        """正常更新掌握分"""
        space = sample_graph["space"]
        array = sample_graph["nodes"]["array"]

        updated = await service.update_mastery(space.id, array.id, 90)

        assert updated.mastery == 90

    @pytest.mark.asyncio
    async def test_update_mastery_boundary_0(
        self, service: GraphService, sample_graph: dict
    ):
        """边界值：0"""
        space = sample_graph["space"]
        node = sample_graph["nodes"]["array"]

        updated = await service.update_mastery(space.id, node.id, 0)
        assert updated.mastery == 0

    @pytest.mark.asyncio
    async def test_update_mastery_boundary_100(
        self, service: GraphService, sample_graph: dict
    ):
        """边界值：100"""
        space = sample_graph["space"]
        node = sample_graph["nodes"]["array"]

        updated = await service.update_mastery(space.id, node.id, 100)
        assert updated.mastery == 100

    @pytest.mark.asyncio
    async def test_update_mastery_invalid_negative(
        self, service: GraphService, sample_graph: dict
    ):
        """负数应报错"""
        space = sample_graph["space"]
        node = sample_graph["nodes"]["array"]

        with pytest.raises(ValueError, match="Mastery must be between 0 and 100"):
            await service.update_mastery(space.id, node.id, -1)

    @pytest.mark.asyncio
    async def test_update_mastery_invalid_over_100(
        self, service: GraphService, sample_graph: dict
    ):
        """超过100应报错"""
        space = sample_graph["space"]
        node = sample_graph["nodes"]["array"]

        with pytest.raises(ValueError, match="Mastery must be between 0 and 100"):
            await service.update_mastery(space.id, node.id, 101)

    @pytest.mark.asyncio
    async def test_update_mastery_node_not_found(
        self, service: GraphService, graph_test_space: Space
    ):
        """节点不存在"""
        fake_id = uuid4()
        with pytest.raises(NodeNotFoundError):
            await service.update_mastery(graph_test_space.id, fake_id, 50)


class TestGraphServiceLearningPath:
    """学习路径生成测试"""

    @pytest_asyncio.fixture
    async def service(self, db_session: AsyncSession) -> GraphService:
        return GraphService(db_session)

    @pytest.mark.asyncio
    async def test_create_learning_path_success(
        self, service: GraphService, sample_graph: dict
    ):
        """正常创建学习路径"""
        space = sample_graph["space"]
        nodes = sample_graph["nodes"]
        node_ids = [nodes["array"].id, nodes["linked_list"].id, nodes["tree"].id]

        edges = await service.create_learning_path(space.id, node_ids)

        assert len(edges) == 2
        assert all(e.type == EdgeType.LEARNING_PATH for e in edges)

    @pytest.mark.asyncio
    async def test_create_learning_path_single_node_raises(
        self, service: GraphService, sample_graph: dict
    ):
        """单节点路径应报错"""
        space = sample_graph["space"]
        node_ids = [sample_graph["nodes"]["array"].id]

        with pytest.raises(ValueError, match="at least 2 nodes"):
            await service.create_learning_path(space.id, node_ids)

    @pytest.mark.asyncio
    async def test_create_learning_path_two_nodes(
        self, service: GraphService, sample_graph: dict
    ):
        """两节点路径（创建1条边）"""
        space = sample_graph["space"]
        nodes = sample_graph["nodes"]
        node_ids = [nodes["array"].id, nodes["linked_list"].id]

        edges = await service.create_learning_path(space.id, node_ids)

        assert len(edges) == 1

    @pytest.mark.asyncio
    async def test_create_learning_path_existing_edge_skipped(
        self, service: GraphService, graph_test_space: Space
    ):
        """已存在边时跳过创建"""
        n1 = await service.create_node(graph_test_space.id, "N1")
        n2 = await service.create_node(graph_test_space.id, "N2")
        n3 = await service.create_node(graph_test_space.id, "N3")

        # 先创建 N1->N2 的 learning_path 边
        edges1 = await service.create_learning_path(graph_test_space.id, [n1.id, n2.id])
        assert len(edges1) == 1

        # 再创建 N1->N2->N3，N1->N2 应该被跳过
        edges2 = await service.create_learning_path(
            graph_test_space.id, [n1.id, n2.id, n3.id]
        )
        assert len(edges2) == 1  # 只有 N2->N3

    @pytest.mark.asyncio
    async def test_create_learning_path_invalid_node(
        self, service: GraphService, sample_graph: dict
    ):
        """序列中包含无效节点"""
        space = sample_graph["space"]
        fake_id = uuid4()

        with pytest.raises(NodeNotFoundError):
            await service.create_learning_path(
                space.id, [sample_graph["nodes"]["array"].id, fake_id]
            )

    @pytest.mark.asyncio
    async def test_create_learning_path_empty_raises(
        self, service: GraphService, graph_test_space: Space
    ):
        """空序列应报错"""
        with pytest.raises(ValueError, match="at least 2 nodes"):
            await service.create_learning_path(graph_test_space.id, [])
