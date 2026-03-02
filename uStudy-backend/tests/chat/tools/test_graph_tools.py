"""GraphToolExecutor 单元测试"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Space, Node, Edge, EdgeType
from chat.tools.graph_tools import GraphToolExecutor, GRAPH_TOOLS
from graph.service import GraphService


class TestGraphToolExecutorBasic:
    """GraphToolExecutor 基础测试"""

    @pytest_asyncio.fixture
    async def executor(
        self, db_session: AsyncSession, graph_test_space: Space
    ) -> GraphToolExecutor:
        """创建工具执行器"""
        return GraphToolExecutor(graph_test_space.id)

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, executor: GraphToolExecutor):
        """未知工具名应返回错误"""
        result = await executor.execute("unknown_tool", {})

        assert result.success is False
        assert "未知的工具" in result.message

    @pytest.mark.asyncio
    async def test_graph_tools_count(self):
        """验证工具数量为10"""
        assert len(GRAPH_TOOLS) == 10

    @pytest.mark.asyncio
    async def test_graph_tools_format(self):
        """验证工具格式符合 OpenAI Function Calling"""
        for tool in GRAPH_TOOLS:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]


class TestGetGraphOverview:
    """get_graph_overview 工具测试"""

    @pytest_asyncio.fixture
    async def executor(
        self, db_session: AsyncSession, graph_test_space: Space
    ) -> GraphToolExecutor:
        return GraphToolExecutor(graph_test_space.id)

    @pytest.mark.asyncio
    async def test_get_graph_overview_empty(
        self, executor: GraphToolExecutor, empty_graph_space: Space, db_session
    ):
        """空图谱概览"""
        exec_empty = GraphToolExecutor(empty_graph_space.id)
        result = await exec_empty.execute("get_graph_overview", {})

        assert result.success is True
        assert result.data == "(空知识图谱)"
        assert "知识图谱为空" in result.message

    @pytest.mark.asyncio
    async def test_get_graph_overview_with_data(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """有数据的图谱概览 - 验证紧凑文本格式"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("get_graph_overview", {})

        assert result.success is True
        # 验证返回的是文本格式
        assert isinstance(result.data, str)
        # 验证包含格式说明
        assert "格式说明" in result.data
        # 验证包含知识树区块
        assert "/basic_knowledge_tree" in result.data
        # 验证包含节点（sample_graph 包含 数据结构、线性结构 等节点）
        assert "数据结构" in result.data
        # 验证统计信息
        assert "7 个节点" in result.message


class TestAddNode:
    """add_node 工具测试"""

    @pytest_asyncio.fixture
    async def executor(
        self, db_session: AsyncSession, graph_test_space: Space
    ) -> GraphToolExecutor:
        return GraphToolExecutor(graph_test_space.id)

    @pytest.mark.asyncio
    async def test_add_node_success(self, executor: GraphToolExecutor):
        """正常添加节点"""
        result = await executor.execute("add_node", {"label": "新节点"})

        assert result.success is True
        assert result.data["label"] == "新节点"
        assert "成功创建节点" in result.message

    @pytest.mark.asyncio
    async def test_add_node_with_mastery(self, executor: GraphToolExecutor):
        """添加带掌握分的节点"""
        result = await executor.execute(
            "add_node", {"label": "带分数节点", "mastery": 75}
        )

        assert result.success is True
        assert result.data["mastery"] == 75

    @pytest.mark.asyncio
    async def test_add_node_mastery_minus_one(self, executor: GraphToolExecutor):
        """-1 表示未学习，转换为 None"""
        result = await executor.execute(
            "add_node", {"label": "未学习", "mastery": -1}
        )

        assert result.success is True
        assert result.data["mastery"] is None

    @pytest.mark.asyncio
    async def test_add_node_empty_label(self, executor: GraphToolExecutor):
        """空标签应失败"""
        result = await executor.execute("add_node", {"label": ""})

        assert result.success is False
        assert "不能为空" in result.message

    @pytest.mark.asyncio
    async def test_add_node_missing_label(self, executor: GraphToolExecutor):
        """缺少标签应失败"""
        result = await executor.execute("add_node", {})

        assert result.success is False


class TestAddEdge:
    """add_edge 工具测试"""

    @pytest_asyncio.fixture
    async def executor(
        self, db_session: AsyncSession, graph_test_space: Space
    ) -> GraphToolExecutor:
        return GraphToolExecutor(graph_test_space.id)

    @pytest.mark.asyncio
    async def test_add_edge_success(self, executor: GraphToolExecutor):
        """正常添加边"""
        # 先创建两个节点
        await executor.execute("add_node", {"label": "源节点"})
        await executor.execute("add_node", {"label": "目标节点"})

        result = await executor.execute("add_edge", {
            "from_node": "源节点",
            "to_node": "目标节点",
        })

        assert result.success is True
        assert "成功创建边" in result.message

    @pytest.mark.asyncio
    async def test_add_edge_all_types(self, executor: GraphToolExecutor):
        """测试所有边类型"""
        await executor.execute("add_node", {"label": "N1"})
        await executor.execute("add_node", {"label": "N2"})
        await executor.execute("add_node", {"label": "N3"})
        await executor.execute("add_node", {"label": "N4"})

        # knowledge_tree
        r1 = await executor.execute("add_edge", {
            "from_node": "N1",
            "to_node": "N2",
            "edge_type": "knowledge_tree",
        })
        assert r1.data["type"] == "knowledge_tree"

        # learning_path
        r2 = await executor.execute("add_edge", {
            "from_node": "N2",
            "to_node": "N3",
            "edge_type": "learning_path",
        })
        assert r2.data["type"] == "learning_path"

        # advanced
        r3 = await executor.execute("add_edge", {
            "from_node": "N3",
            "to_node": "N4",
            "edge_type": "advanced",
        })
        assert r3.data["type"] == "advanced"

    @pytest.mark.asyncio
    async def test_add_edge_node_not_found(self, executor: GraphToolExecutor):
        """节点不存在"""
        result = await executor.execute("add_edge", {
            "from_node": "不存在的节点1",
            "to_node": "不存在的节点2",
        })

        assert result.success is False
        assert "节点不存在" in result.message

    @pytest.mark.asyncio
    async def test_add_edge_missing_params(self, executor: GraphToolExecutor):
        """缺少必选参数"""
        result = await executor.execute("add_edge", {})

        assert result.success is False


class TestDeleteNode:
    """delete_node 工具测试"""

    @pytest.mark.asyncio
    async def test_delete_node_success(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """正常删除节点"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("delete_node", {"node_name": "数组"})

        assert result.success is True
        assert result.data["deleted_node_name"] == "数组"

    @pytest.mark.asyncio
    async def test_delete_node_not_found(
        self, db_session: AsyncSession, graph_test_space: Space
    ):
        """删除不存在的节点"""
        executor = GraphToolExecutor(graph_test_space.id)

        result = await executor.execute("delete_node", {"node_name": "不存在的节点"})

        assert result.success is False
        assert "节点不存在" in result.message


class TestDeleteEdge:
    """delete_edge 工具测试"""

    @pytest.mark.asyncio
    async def test_delete_edge_success(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """正常删除边"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        # sample_graph 中有 数据结构->线性结构 的边
        result = await executor.execute("delete_edge", {
            "from_node": "数据结构",
            "to_node": "线性结构",
        })

        assert result.success is True
        assert result.data["from_node"] == "数据结构"
        assert result.data["to_node"] == "线性结构"

    @pytest.mark.asyncio
    async def test_delete_edge_not_found(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """删除不存在的边"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("delete_edge", {
            "from_node": "数组",
            "to_node": "树",
        })

        assert result.success is False
        assert "边不存在" in result.message

    @pytest.mark.asyncio
    async def test_delete_edge_node_not_found(
        self, db_session: AsyncSession, graph_test_space: Space
    ):
        """节点不存在"""
        executor = GraphToolExecutor(graph_test_space.id)

        result = await executor.execute("delete_edge", {
            "from_node": "不存在节点1",
            "to_node": "不存在节点2",
        })

        assert result.success is False
        assert "节点不存在" in result.message


class TestUpdateMastery:
    """update_mastery 工具测试"""

    @pytest.mark.asyncio
    async def test_update_mastery_success(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """正常更新掌握分"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("update_mastery", {
            "node_name": "数组",
            "mastery": 95,
        })

        assert result.success is True
        assert result.data["mastery"] == 95

    @pytest.mark.asyncio
    async def test_update_mastery_boundary_0(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """边界值 0"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("update_mastery", {
            "node_name": "数组",
            "mastery": 0,
        })

        assert result.success is True
        assert result.data["mastery"] == 0

    @pytest.mark.asyncio
    async def test_update_mastery_boundary_100(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """边界值 100"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("update_mastery", {
            "node_name": "数组",
            "mastery": 100,
        })

        assert result.success is True
        assert result.data["mastery"] == 100

    @pytest.mark.asyncio
    async def test_update_mastery_invalid_negative(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """负数应失败"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("update_mastery", {
            "node_name": "数组",
            "mastery": -5,
        })

        assert result.success is False
        assert "参数错误" in result.message

    @pytest.mark.asyncio
    async def test_update_mastery_invalid_over_100(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """超过100应失败"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("update_mastery", {
            "node_name": "数组",
            "mastery": 150,
        })

        assert result.success is False

    @pytest.mark.asyncio
    async def test_update_mastery_missing_params(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """缺少必选参数"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("update_mastery", {"node_name": "数组"})

        assert result.success is False
        assert "不能为空" in result.message

    @pytest.mark.asyncio
    async def test_update_mastery_node_not_found(
        self, db_session: AsyncSession, graph_test_space: Space
    ):
        """节点不存在"""
        executor = GraphToolExecutor(graph_test_space.id)

        result = await executor.execute("update_mastery", {
            "node_name": "不存在的节点",
            "mastery": 50,
        })

        assert result.success is False
        assert "节点不存在" in result.message


class TestGetChildNodes:
    """get_child_nodes 工具测试"""

    @pytest.mark.asyncio
    async def test_get_child_nodes_success(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """正常获取子节点 - 返回文本格式"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("get_child_nodes", {"node_name": "数据结构"})

        assert result.success is True
        assert isinstance(result.data, str)
        assert "/children_of: 数据结构" in result.data
        assert "* 数据结构 [" in result.data
        assert "** 线性结构 [" in result.data
        assert "** 树 [" in result.data

    @pytest.mark.asyncio
    async def test_get_child_nodes_with_max_depth(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """带深度限制获取子节点"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("get_child_nodes", {
            "node_name": "数据结构",
            "max_depth": 1,
        })

        assert result.success is True
        assert isinstance(result.data, str)
        # 深度1时不应包含第三层节点（数组、链表）
        assert "** 线性结构 [" in result.data
        assert "*** " not in result.data  # 深度1时没有第三层

    @pytest.mark.asyncio
    async def test_get_child_nodes_leaf(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """叶子节点无子节点"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("get_child_nodes", {"node_name": "数组"})

        assert result.success is True
        assert isinstance(result.data, str)
        assert "/children_of: 数组" in result.data
        assert "(无子节点)" in result.data
        assert "没有子节点" in result.message

    @pytest.mark.asyncio
    async def test_get_child_nodes_not_found(
        self, db_session: AsyncSession, graph_test_space: Space
    ):
        """节点不存在"""
        executor = GraphToolExecutor(graph_test_space.id)

        result = await executor.execute("get_child_nodes", {"node_name": "不存在的节点"})

        assert result.success is False
        assert "节点不存在" in result.message


class TestGetParentNodes:
    """get_parent_nodes 工具测试"""

    @pytest.mark.asyncio
    async def test_get_parent_nodes_success(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """正常获取父节点 - 返回文本格式"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("get_parent_nodes", {"node_name": "数组"})

        assert result.success is True
        assert isinstance(result.data, str)
        assert "/parents_of: 数组" in result.data
        assert "- 线性结构 [" in result.data
        assert "1 个父节点" in result.message

    @pytest.mark.asyncio
    async def test_get_parent_nodes_root(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """根节点无父节点"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("get_parent_nodes", {"node_name": "数据结构"})

        assert result.success is True
        assert isinstance(result.data, str)
        assert "/parents_of: 数据结构" in result.data
        assert "(无父节点)" in result.data


class TestGetSiblingNodes:
    """get_sibling_nodes 工具测试"""

    @pytest.mark.asyncio
    async def test_get_sibling_nodes_success(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """正常获取兄弟节点 - 返回文本格式"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("get_sibling_nodes", {"node_name": "数组"})

        assert result.success is True
        assert isinstance(result.data, str)
        assert "/siblings_of: 数组" in result.data
        assert "- 链表 [" in result.data
        assert "1 个兄弟节点" in result.message

    @pytest.mark.asyncio
    async def test_get_sibling_nodes_root(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """根节点无兄弟"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("get_sibling_nodes", {"node_name": "数据结构"})

        assert result.success is True
        assert isinstance(result.data, str)
        assert "/siblings_of: 数据结构" in result.data
        assert "(无兄弟节点)" in result.data


class TestGenerateLearningPath:
    """generate_learning_path 工具测试"""

    @pytest.mark.asyncio
    async def test_generate_learning_path_success(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """正常生成学习路径"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("generate_learning_path", {
            "node_sequence": "数组,链表,树",
        })

        assert result.success is True
        assert result.data["edges_created"] == 2
        assert len(result.data["path"]) == 3
        assert result.data["path"] == ["数组", "链表", "树"]

    @pytest.mark.asyncio
    async def test_generate_learning_path_single_node(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """单节点路径应失败"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("generate_learning_path", {
            "node_sequence": "数组",
        })

        assert result.success is False
        assert "至少需要 2 个节点" in result.message

    @pytest.mark.asyncio
    async def test_generate_learning_path_node_not_found(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """节点不存在"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("generate_learning_path", {
            "node_sequence": "数组,不存在的节点,树",
        })

        assert result.success is False
        assert "节点不存在" in result.message

    @pytest.mark.asyncio
    async def test_generate_learning_path_empty(
        self, db_session: AsyncSession, graph_test_space: Space
    ):
        """空序列"""
        executor = GraphToolExecutor(graph_test_space.id)

        result = await executor.execute("generate_learning_path", {
            "node_sequence": "",
        })

        assert result.success is False


class TestToolExceptionHandling:
    """工具异常处理测试"""

    @pytest.mark.asyncio
    async def test_node_not_found_error(
        self, db_session: AsyncSession, graph_test_space: Space
    ):
        """节点不存在错误"""
        executor = GraphToolExecutor(graph_test_space.id)

        result = await executor.execute("get_child_nodes", {"node_name": "不存在的节点"})

        assert result.success is False
        assert "节点不存在" in result.message

    @pytest.mark.asyncio
    async def test_duplicate_node_error(
        self, db_session: AsyncSession, graph_test_space: Space
    ):
        """重复节点错误"""
        executor = GraphToolExecutor(graph_test_space.id)

        await executor.execute("add_node", {"label": "唯一节点"})
        result = await executor.execute("add_node", {"label": "唯一节点"})

        assert result.success is False
        assert "节点已存在" in result.message

    @pytest.mark.asyncio
    async def test_value_error(
        self, db_session: AsyncSession, sample_graph: dict
    ):
        """参数错误"""
        space = sample_graph["space"]
        executor = GraphToolExecutor(space.id)

        result = await executor.execute("update_mastery", {
            "node_name": "数组",
            "mastery": -100,
        })

        assert result.success is False
        assert "参数错误" in result.message
