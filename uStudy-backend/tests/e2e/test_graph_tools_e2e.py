"""知识图谱工具端到端测试

这些测试验证完整的业务流程，模拟真实用户操作。
需要数据库环境，但使用 mock LLM 客户端。
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Space, User
from chat.tools.graph_tools import GraphToolExecutor, GRAPH_TOOLS


class TestKnowledgeGraphE2E:
    """知识图谱端到端测试"""

    @pytest_asyncio.fixture
    async def executor(
        self, db_session: AsyncSession, graph_test_space: Space
    ) -> GraphToolExecutor:
        return GraphToolExecutor(graph_test_space.id)

    @pytest.mark.asyncio
    async def test_build_data_structure_knowledge_graph(
        self, executor: GraphToolExecutor
    ):
        """构建数据结构知识图谱的完整流程"""
        # 1. 创建根节点
        r_root = await executor.execute("add_node", {
            "label": "数据结构",
            "mastery": 0,
        })
        assert r_root.success is True
        root_id = r_root.data["id"]

        # 2. 创建一级分类
        categories = ["线性结构", "非线性结构", "查找", "排序"]
        category_ids = {}

        for cat in categories:
            r = await executor.execute("add_node", {"label": cat, "mastery": 0})
            assert r.success is True
            category_ids[cat] = r.data["id"]

            # 连接到根节点
            r_edge = await executor.execute("add_edge", {
                "from_node_id": root_id,
                "to_node_id": category_ids[cat],
                "edge_type": "knowledge_tree",
            })
            assert r_edge.success is True

        # 3. 创建线性结构下的子节点
        linear_nodes = ["数组", "链表", "栈", "队列"]
        linear_ids = {}

        for node in linear_nodes:
            r = await executor.execute("add_node", {"label": node})
            assert r.success is True
            linear_ids[node] = r.data["id"]

            r_edge = await executor.execute("add_edge", {
                "from_node_id": category_ids["线性结构"],
                "to_node_id": linear_ids[node],
                "edge_type": "knowledge_tree",
            })
            assert r_edge.success is True

        # 4. 创建非线性结构下的子节点
        nonlinear_nodes = ["树", "图", "堆"]

        for node in nonlinear_nodes:
            r = await executor.execute("add_node", {"label": node})
            assert r.success is True
            node_id = r.data["id"]

            r_edge = await executor.execute("add_edge", {
                "from_node_id": category_ids["非线性结构"],
                "to_node_id": node_id,
                "edge_type": "knowledge_tree",
            })
            assert r_edge.success is True

        # 5. 添加高级连接（跨分类关联）
        # 队列 -> BFS (广度优先搜索基于队列)
        r_bfs = await executor.execute("add_node", {"label": "BFS"})
        await executor.execute("add_edge", {
            "from_node_id": linear_ids["队列"],
            "to_node_id": r_bfs.data["id"],
            "edge_type": "advanced",
        })

        # 6. 验证图谱结构（文本格式）
        r_overview = await executor.execute("get_graph_overview", {})
        assert r_overview.success is True

        # 应该有: 1 根 + 4 分类 + 4 线性 + 3 非线性 + 1 BFS = 13 节点
        assert "13 个节点" in r_overview.message

        # 7. 验证子节点查询
        r_children = await executor.execute("get_child_nodes", {
            "node_id": root_id,
            "max_depth": 1,
        })
        assert len(r_children.data["children"]) == 4

        # 8. 验证兄弟节点
        r_siblings = await executor.execute("get_sibling_nodes", {
            "node_id": linear_ids["数组"],
        })
        assert len(r_siblings.data["siblings"]) == 3

    @pytest.mark.asyncio
    async def test_learning_path_creation_flow(
        self, executor: GraphToolExecutor
    ):
        """学习路径创建流程"""
        # 1. 创建知识点序列
        topics = ["Python 基础", "变量与类型", "控制流", "函数", "类与对象"]
        node_ids = []

        for topic in topics:
            r = await executor.execute("add_node", {"label": topic})
            assert r.success is True
            node_ids.append(r.data["id"])

        # 2. 创建知识树结构
        for i in range(len(node_ids) - 1):
            r = await executor.execute("add_edge", {
                "from_node_id": node_ids[i],
                "to_node_id": node_ids[i + 1],
                "edge_type": "knowledge_tree",
            })
            assert r.success is True

        # 3. 生成自定义学习路径（非线性）
        custom_path = [node_ids[0], node_ids[2], node_ids[4]]  # 跳过一些
        path_sequence = ",".join(custom_path)

        r_path = await executor.execute("generate_learning_path", {
            "node_sequence": path_sequence,
        })
        assert r_path.success is True
        assert r_path.data["edges_created"] == 2

        # 4. 验证学习路径边（文本格式中有 /learning_path 区块）
        r_overview = await executor.execute("get_graph_overview", {})
        assert "/learning_path" in r_overview.data

    @pytest.mark.asyncio
    async def test_mastery_tracking_flow(
        self, executor: GraphToolExecutor
    ):
        """掌握度跟踪流程"""
        # 1. 创建课程节点
        courses = [
            ("入门课程", -1),  # 未开始
            ("基础课程", 30),  # 进行中
            ("进阶课程", 80),  # 接近完成
            ("高级课程", 100), # 已完成
        ]

        node_ids = []
        for name, mastery in courses:
            r = await executor.execute("add_node", {
                "label": name,
                "mastery": mastery,
            })
            assert r.success is True
            node_ids.append(r.data["id"])

            # 验证掌握度
            if mastery == -1:
                assert r.data["mastery"] is None
            else:
                assert r.data["mastery"] == mastery

        # 2. 更新掌握度
        r_update = await executor.execute("update_mastery", {
            "node_id": node_ids[0],  # 入门课程
            "mastery": 50,
        })
        assert r_update.success is True
        assert r_update.data["mastery"] == 50

        # 3. 批量更新并验证
        for i, new_mastery in enumerate([60, 70, 90, 100]):
            await executor.execute("update_mastery", {
                "node_id": node_ids[i],
                "mastery": new_mastery,
            })

        # 4. 验证最终状态（文本格式包含掌握分）
        r_overview = await executor.execute("get_graph_overview", {})
        # 验证返回的是文本格式
        assert isinstance(r_overview.data, str)
        assert "/basic_knowledge_tree" in r_overview.data

    @pytest.mark.asyncio
    async def test_graph_modification_and_recovery(
        self, executor: GraphToolExecutor
    ):
        """图谱修改和恢复测试"""
        # 1. 创建初始图谱
        nodes = ["A", "B", "C", "D"]
        node_ids = {}

        for name in nodes:
            r = await executor.execute("add_node", {"label": name})
            node_ids[name] = r.data["id"]

        # A -> B -> C -> D (链式)
        for i in range(len(nodes) - 1):
            await executor.execute("add_edge", {
                "from_node_id": node_ids[nodes[i]],
                "to_node_id": node_ids[nodes[i + 1]],
            })

        # 2. 验证初始结构（文本格式）
        r1 = await executor.execute("get_graph_overview", {})
        assert "4 个节点" in r1.message
        assert "3 条边" in r1.message

        # 3. 删除中间节点 B
        await executor.execute("delete_node", {"node_id": node_ids["B"]})

        # 4. 验证删除后结构
        r2 = await executor.execute("get_graph_overview", {})
        assert "3 个节点" in r2.message  # A, C, D
        assert "1 条边" in r2.message  # 只剩 C -> D

        # 5. 重建连接
        r_new_b = await executor.execute("add_node", {"label": "B_new"})
        await executor.execute("add_edge", {
            "from_node_id": node_ids["A"],
            "to_node_id": r_new_b.data["id"],
        })
        await executor.execute("add_edge", {
            "from_node_id": r_new_b.data["id"],
            "to_node_id": node_ids["C"],
        })

        # 6. 验证恢复后结构
        r3 = await executor.execute("get_graph_overview", {})
        assert "4 个节点" in r3.message
        assert "3 条边" in r3.message


class TestToolChainE2E:
    """工具链端到端测试"""

    @pytest_asyncio.fixture
    async def executor(
        self, db_session: AsyncSession, graph_test_space: Space
    ) -> GraphToolExecutor:
        return GraphToolExecutor(graph_test_space.id)

    @pytest.mark.asyncio
    async def test_all_10_tools_integration(
        self, executor: GraphToolExecutor
    ):
        """验证所有 10 个工具的集成"""
        # 验证工具数量
        assert len(GRAPH_TOOLS) == 10

        tool_names = [t["function"]["name"] for t in GRAPH_TOOLS]
        expected_tools = [
            "get_graph_overview",
            "add_node",
            "add_edge",
            "delete_node",
            "delete_edge",
            "update_mastery",
            "get_child_nodes",
            "get_parent_nodes",
            "get_sibling_nodes",
            "generate_learning_path",
        ]

        for tool in expected_tools:
            assert tool in tool_names

        # 逐个测试每个工具
        results = {}

        # 1. get_graph_overview (空)
        results["overview_empty"] = await executor.execute("get_graph_overview", {})
        assert results["overview_empty"].success is True

        # 2. add_node
        results["add_root"] = await executor.execute("add_node", {"label": "Root"})
        assert results["add_root"].success is True
        root_id = results["add_root"].data["id"]

        results["add_child1"] = await executor.execute("add_node", {"label": "Child1"})
        results["add_child2"] = await executor.execute("add_node", {"label": "Child2"})
        child1_id = results["add_child1"].data["id"]
        child2_id = results["add_child2"].data["id"]

        # 3. add_edge
        results["add_edge1"] = await executor.execute("add_edge", {
            "from_node_id": root_id,
            "to_node_id": child1_id,
        })
        results["add_edge2"] = await executor.execute("add_edge", {
            "from_node_id": root_id,
            "to_node_id": child2_id,
        })
        edge2_id = results["add_edge2"].data["id"]
        assert results["add_edge1"].success is True

        # 4. update_mastery
        results["update_mastery"] = await executor.execute("update_mastery", {
            "node_id": child1_id,
            "mastery": 75,
        })
        assert results["update_mastery"].success is True

        # 5. get_child_nodes
        results["get_children"] = await executor.execute("get_child_nodes", {
            "node_id": root_id,
        })
        assert len(results["get_children"].data["children"]) == 2

        # 6. get_parent_nodes
        results["get_parents"] = await executor.execute("get_parent_nodes", {
            "node_id": child1_id,
        })
        assert len(results["get_parents"].data["parents"]) == 1

        # 7. get_sibling_nodes
        results["get_siblings"] = await executor.execute("get_sibling_nodes", {
            "node_id": child1_id,
        })
        assert len(results["get_siblings"].data["siblings"]) == 1

        # 8. generate_learning_path
        results["learning_path"] = await executor.execute("generate_learning_path", {
            "node_sequence": f"{root_id},{child1_id},{child2_id}",
        })
        assert results["learning_path"].success is True

        # 9. delete_edge
        results["delete_edge"] = await executor.execute("delete_edge", {
            "edge_id": edge2_id,
        })
        assert results["delete_edge"].success is True

        # 10. delete_node
        results["delete_node"] = await executor.execute("delete_node", {
            "node_id": child2_id,
        })
        assert results["delete_node"].success is True

        # 最终验证
        results["final_overview"] = await executor.execute("get_graph_overview", {})
        assert len(results["final_overview"].data["nodes"]) == 2  # Root, Child1

    @pytest.mark.asyncio
    async def test_batch_tool_execution(
        self, executor: GraphToolExecutor
    ):
        """批量工具执行测试（顺序执行，验证批量操作）"""
        # 创建根节点
        r_root = await executor.execute("add_node", {"label": "批量测试根"})
        root_id = r_root.data["id"]

        # 顺序创建多个子节点（SQLAlchemy AsyncSession 不支持真正的并发）
        successful = []
        for i in range(10):
            r = await executor.execute("add_node", {"label": f"批量子节点{i}"})
            if r.success:
                await executor.execute("add_edge", {
                    "from_node_id": root_id,
                    "to_node_id": r.data["id"],
                })
                successful.append(r)

        # 验证所有创建成功
        assert len(successful) == 10

        # 验证图谱结构
        r_overview = await executor.execute("get_graph_overview", {})
        assert len(r_overview.data["nodes"]) == 11  # 1 root + 10 children
