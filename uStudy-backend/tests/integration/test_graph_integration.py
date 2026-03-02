"""知识图谱集成测试"""

import asyncio
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Node, Edge, EdgeType, Space, User
from graph.service import GraphService
from chat.tools.graph_tools import GraphToolExecutor
from graph.exceptions import NodeNotFoundError


class TestGraphDBIntegration:
    """知识图谱数据库集成测试"""

    @pytest_asyncio.fixture
    async def graph_service(self, db_session: AsyncSession) -> GraphService:
        return GraphService(db_session)

    @pytest.mark.asyncio
    async def test_node_edge_cascade_delete(
        self,
        graph_service: GraphService,
        graph_test_space: Space,
        db_session: AsyncSession,
    ):
        """删除节点级联删除边"""
        # 创建节点
        parent = await graph_service.create_node(graph_test_space.id, "父节点")
        child1 = await graph_service.create_node(graph_test_space.id, "子节点1")
        child2 = await graph_service.create_node(graph_test_space.id, "子节点2")

        # 创建边
        await graph_service.create_edge(
            graph_test_space.id, parent.id, child1.id, "knowledge_tree"
        )
        await graph_service.create_edge(
            graph_test_space.id, parent.id, child2.id, "knowledge_tree"
        )
        await graph_service.create_edge(
            graph_test_space.id, child1.id, child2.id, "advanced"
        )

        # 验证边存在
        graph = await graph_service.get_graph(graph_test_space.id)
        assert len(graph["edges"]) == 3

        # 删除 child1
        await graph_service.delete_node(graph_test_space.id, child1.id)

        # 验证相关边已删除
        graph_after = await graph_service.get_graph(graph_test_space.id)
        assert len(graph_after["edges"]) == 1  # 只剩 parent -> child2

    @pytest.mark.asyncio
    async def test_space_isolation(
        self,
        graph_service: GraphService,
        db_session: AsyncSession,
        graph_test_user: User,
    ):
        """不同学习空间数据隔离"""
        # 创建两个空间
        space1 = Space(id=uuid4(), user_id=graph_test_user.id, name="Space1", color="#111")
        space2 = Space(id=uuid4(), user_id=graph_test_user.id, name="Space2", color="#222")
        db_session.add(space1)
        db_session.add(space2)
        await db_session.commit()

        # 在两个空间创建同名节点
        node1 = await graph_service.create_node(space1.id, "数据结构")
        node2 = await graph_service.create_node(space2.id, "数据结构")

        # 验证是不同的节点
        assert node1.id != node2.id
        assert node1.space_id != node2.space_id

        # 空间1的查询不应该返回空间2的节点
        graph1 = await graph_service.get_graph(space1.id)
        graph2 = await graph_service.get_graph(space2.id)

        assert len(graph1["nodes"]) == 1
        assert len(graph2["nodes"]) == 1
        assert graph1["nodes"][0]["id"] != graph2["nodes"][0]["id"]

    @pytest.mark.asyncio
    async def test_sequential_batch_node_creation(
        self,
        db_session: AsyncSession,
        graph_test_space: Space,
    ):
        """批量顺序创建节点（SQLAlchemy AsyncSession 不支持真正的并发）"""
        service = GraphService(db_session)

        # 顺序创建多个节点
        nodes = []
        for i in range(5):
            node = await service.create_node(graph_test_space.id, f"Node_{i}")
            nodes.append(node)

        # 验证所有节点创建成功
        assert len(nodes) == 5
        assert all(isinstance(n, Node) for n in nodes)

    @pytest.mark.asyncio
    async def test_transaction_rollback(
        self,
        graph_service: GraphService,
        graph_test_space: Space,
        db_session: AsyncSession,
    ):
        """事务回滚测试"""
        # 创建初始节点
        node = await graph_service.create_node(graph_test_space.id, "测试节点")

        # 尝试创建重复节点（应该失败）
        try:
            await graph_service.create_node(graph_test_space.id, "测试节点")
        except Exception:
            pass

        # 验证原节点仍然存在
        graph = await graph_service.get_graph(graph_test_space.id)
        assert len(graph["nodes"]) == 1
        assert graph["nodes"][0]["label"] == "测试节点"


class TestAgentToolsIntegration:
    """Agent 与工具集成测试"""

    @pytest.mark.asyncio
    async def test_tool_chain_execution(
        self,
        db_session: AsyncSession,
        graph_test_space: Space,
    ):
        """工具链执行：add_node -> add_edge -> get_graph_overview"""
        executor = GraphToolExecutor(graph_test_space.id)

        # 1. 添加节点
        result1 = await executor.execute("add_node", {"label": "节点A"})
        assert result1.success is True

        result2 = await executor.execute("add_node", {"label": "节点B"})
        assert result2.success is True

        # 2. 添加边
        result3 = await executor.execute("add_edge", {
            "from_node": "节点A",
            "to_node": "节点B",
            "edge_type": "knowledge_tree",
        })
        assert result3.success is True

        # 3. 获取概览（文本格式）
        result4 = await executor.execute("get_graph_overview", {})
        assert result4.success is True
        assert "2 个节点" in result4.message
        assert "1 条边" in result4.message

    @pytest.mark.asyncio
    async def test_complete_graph_manipulation(
        self,
        db_session: AsyncSession,
        graph_test_space: Space,
    ):
        """完整图谱操作流程"""
        executor = GraphToolExecutor(graph_test_space.id)

        # 1. 验证初始为空
        r0 = await executor.execute("get_graph_overview", {})
        assert r0.data == "(空知识图谱)"

        # 2. 添加 5 个节点
        node_names = []
        for i in range(5):
            name = f"知识点{i+1}"
            r = await executor.execute("add_node", {"label": name})
            assert r.success is True
            node_names.append(name)

        # 3. 添加 4 条边（形成链）
        for i in range(4):
            r = await executor.execute("add_edge", {
                "from_node": node_names[i],
                "to_node": node_names[i + 1],
            })
            assert r.success is True

        # 4. 获取子节点
        r_children = await executor.execute("get_child_nodes", {
            "node_name": node_names[0],
            "max_depth": 2,
        })
        assert r_children.success is True
        assert len(r_children.data["children"]) == 1

        # 5. 更新掌握分
        r_mastery = await executor.execute("update_mastery", {
            "node_name": node_names[0],
            "mastery": 85,
        })
        assert r_mastery.success is True
        assert r_mastery.data["mastery"] == 85

        # 6. 生成学习路径
        path_sequence = ",".join(node_names[:3])
        r_path = await executor.execute("generate_learning_path", {
            "node_sequence": path_sequence,
        })
        assert r_path.success is True

        # 7. 删除一个节点
        r_delete = await executor.execute("delete_node", {"node_name": node_names[4]})
        assert r_delete.success is True

        # 8. 最终验证
        r_final = await executor.execute("get_graph_overview", {})
        assert "4 个节点" in r_final.message

    @pytest.mark.asyncio
    async def test_error_recovery(
        self,
        db_session: AsyncSession,
        graph_test_space: Space,
    ):
        """错误恢复测试"""
        executor = GraphToolExecutor(graph_test_space.id)

        # 创建一个节点
        r1 = await executor.execute("add_node", {"label": "有效节点"})
        assert r1.success is True

        # 尝试一些无效操作
        r_invalid1 = await executor.execute("delete_node", {"node_name": "不存在的节点"})
        assert r_invalid1.success is False

        r_invalid2 = await executor.execute("update_mastery", {
            "node_name": "有效节点",
            "mastery": 200,  # 超出范围
        })
        assert r_invalid2.success is False

        # 验证系统仍然正常工作
        r_verify = await executor.execute("get_graph_overview", {})
        assert r_verify.success is True
        assert "1 个节点" in r_verify.message


class TestPerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_large_graph_query(
        self,
        db_session: AsyncSession,
        graph_test_space: Space,
    ):
        """大图谱查询性能"""
        service = GraphService(db_session)

        # 创建 100 个节点
        nodes = []
        for i in range(100):
            node = await service.create_node(graph_test_space.id, f"Node_{i}")
            nodes.append(node)

        # 创建树形边（每个节点最多 3 个子节点）
        for i, node in enumerate(nodes[:-1]):
            if i * 3 + 1 < len(nodes):
                await service.create_edge(
                    graph_test_space.id,
                    node.id,
                    nodes[min(i * 3 + 1, len(nodes) - 1)].id,
                )

        # 测试查询性能
        import time

        start = time.time()
        graph = await service.get_graph(graph_test_space.id)
        elapsed = time.time() - start

        assert len(graph["nodes"]) == 100
        assert elapsed < 2.0  # 应该在 2 秒内完成

    @pytest.mark.asyncio
    async def test_recursive_query_performance(
        self,
        db_session: AsyncSession,
        graph_test_space: Space,
    ):
        """递归查询性能测试"""
        service = GraphService(db_session)

        # 创建深度为 5 的树
        root = await service.create_node(graph_test_space.id, "Root")
        current = root
        for i in range(5):
            child = await service.create_node(graph_test_space.id, f"Level_{i}")
            await service.create_edge(graph_test_space.id, current.id, child.id)
            current = child

        import time

        start = time.time()
        children = await service.get_children(graph_test_space.id, root.id, max_depth=-1)
        elapsed = time.time() - start

        assert elapsed < 1.0  # 应该在 1 秒内完成


class TestBoundaryConditions:
    """边界条件测试"""

    @pytest.mark.asyncio
    async def test_empty_graph_operations(
        self,
        db_session: AsyncSession,
        empty_graph_space: Space,
    ):
        """空图谱操作"""
        executor = GraphToolExecutor(empty_graph_space.id)

        # 概览应该返回空
        r = await executor.execute("get_graph_overview", {})
        assert r.success is True
        assert r.data == "(空知识图谱)"

    @pytest.mark.asyncio
    async def test_single_node_operations(
        self,
        db_session: AsyncSession,
        graph_test_space: Space,
    ):
        """单节点操作"""
        executor = GraphToolExecutor(graph_test_space.id)

        # 创建单个节点
        r1 = await executor.execute("add_node", {"label": "孤立节点"})

        # 获取子节点（应为空）
        r2 = await executor.execute("get_child_nodes", {"node_name": "孤立节点"})
        assert r2.data["children"] == []

        # 获取父节点（应为空）
        r3 = await executor.execute("get_parent_nodes", {"node_name": "孤立节点"})
        assert r3.data["parents"] == []

        # 获取兄弟节点（应为空）
        r4 = await executor.execute("get_sibling_nodes", {"node_name": "孤立节点"})
        assert r4.data["siblings"] == []
