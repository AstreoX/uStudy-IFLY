"""数据库集成测试"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    AgentTask,
    AgentTaskStatus,
    AgentTaskType,
    Edge,
    EdgeType,
    Node,
    Space,
    User,
)


class TestTaskLifecycleStates:
    """任务状态流转测试"""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """创建测试用户"""
        user = User(
            id=uuid4(),
            email="lifecycle@test.com",
            nickname="Lifecycle User",
        )
        db_session.add(user)
        await db_session.commit()
        return user

    @pytest_asyncio.fixture
    async def test_space(self, db_session: AsyncSession, test_user: User) -> Space:
        """创建测试学习空间"""
        space = Space(
            id=uuid4(),
            user_id=test_user.id,
            name="Lifecycle Space",
            color="#123456",
        )
        db_session.add(space)
        await db_session.commit()
        return space

    @pytest.mark.asyncio
    async def test_task_created_with_pending_status(
        self, db_session: AsyncSession, test_user: User, test_space: Space
    ):
        """测试任务创建时状态为 PENDING"""
        task = AgentTask(
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_KNOWLEDGE_GRAPH,
            input_data={"topic": "Test"},
        )
        db_session.add(task)
        await db_session.commit()

        # 刷新获取数据库中的值
        await db_session.refresh(task)

        assert task.status == AgentTaskStatus.PENDING
        assert task.started_at is None
        assert task.completed_at is None

    @pytest.mark.asyncio
    async def test_task_state_transition_to_running(
        self, db_session: AsyncSession, test_user: User, test_space: Space
    ):
        """测试任务状态转换到 RUNNING"""
        task = AgentTask(
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_KNOWLEDGE_GRAPH,
            input_data={"topic": "Test"},
        )
        db_session.add(task)
        await db_session.commit()

        # 更新状态
        task.status = AgentTaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        await db_session.commit()
        await db_session.refresh(task)

        assert task.status == AgentTaskStatus.RUNNING
        assert task.started_at is not None
        assert task.completed_at is None

    @pytest.mark.asyncio
    async def test_task_state_transition_to_done(
        self, db_session: AsyncSession, test_user: User, test_space: Space
    ):
        """测试任务状态转换到 DONE"""
        task = AgentTask(
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_KNOWLEDGE_GRAPH,
            input_data={"topic": "Test"},
            status=AgentTaskStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(task)
        await db_session.commit()

        # 更新状态
        task.status = AgentTaskStatus.DONE
        task.completed_at = datetime.now(timezone.utc)
        task.output_data = {"space_id": str(test_space.id), "node_count": 5, "edge_count": 4}
        await db_session.commit()
        await db_session.refresh(task)

        assert task.status == AgentTaskStatus.DONE
        assert task.completed_at is not None
        assert task.output_data["node_count"] == 5

    @pytest.mark.asyncio
    async def test_task_state_transition_to_failed(
        self, db_session: AsyncSession, test_user: User, test_space: Space
    ):
        """测试任务状态转换到 FAILED"""
        task = AgentTask(
            user_id=test_user.id,
            space_id=test_space.id,
            task_type=AgentTaskType.GENERATE_KNOWLEDGE_GRAPH,
            input_data={"topic": "Test"},
            status=AgentTaskStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(task)
        await db_session.commit()

        # 更新状态
        task.status = AgentTaskStatus.FAILED
        task.completed_at = datetime.now(timezone.utc)
        task.error_message = "LLM 调用失败"
        await db_session.commit()
        await db_session.refresh(task)

        assert task.status == AgentTaskStatus.FAILED
        assert task.error_message == "LLM 调用失败"


class TestNodesEdgesRelationship:
    """节点边关系完整性测试"""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """创建测试用户"""
        user = User(
            id=uuid4(),
            email="relationship@test.com",
            nickname="Relationship User",
        )
        db_session.add(user)
        await db_session.commit()
        return user

    @pytest_asyncio.fixture
    async def test_space(self, db_session: AsyncSession, test_user: User) -> Space:
        """创建测试学习空间"""
        space = Space(
            id=uuid4(),
            user_id=test_user.id,
            name="Relationship Space",
            color="#654321",
        )
        db_session.add(space)
        await db_session.commit()
        return space

    @pytest.mark.asyncio
    async def test_nodes_belong_to_space(
        self, db_session: AsyncSession, test_space: Space
    ):
        """测试节点属于正确的空间"""
        node1 = Node(space_id=test_space.id, label="Node 1", mastery=50)
        node2 = Node(space_id=test_space.id, label="Node 2", mastery=75)
        db_session.add_all([node1, node2])
        await db_session.commit()

        result = await db_session.execute(
            select(Node).where(Node.space_id == test_space.id)
        )
        nodes = result.scalars().all()

        assert len(nodes) == 2
        assert all(n.space_id == test_space.id for n in nodes)

    @pytest.mark.asyncio
    async def test_edges_reference_valid_nodes(
        self, db_session: AsyncSession, test_space: Space
    ):
        """测试边引用有效的节点"""
        node1 = Node(space_id=test_space.id, label="Source", mastery=50)
        node2 = Node(space_id=test_space.id, label="Target", mastery=75)
        db_session.add_all([node1, node2])
        await db_session.flush()

        edge = Edge(
            space_id=test_space.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            type=EdgeType.KNOWLEDGE_TREE,
        )
        db_session.add(edge)
        await db_session.commit()

        # 验证边的节点引用
        result = await db_session.execute(
            select(Edge).where(Edge.space_id == test_space.id)
        )
        edges = result.scalars().all()

        assert len(edges) == 1
        assert edges[0].from_node_id == node1.id
        assert edges[0].to_node_id == node2.id

    @pytest.mark.asyncio
    async def test_multiple_edge_types(
        self, db_session: AsyncSession, test_space: Space
    ):
        """测试多种边类型"""
        node1 = Node(space_id=test_space.id, label="A", mastery=50)
        node2 = Node(space_id=test_space.id, label="B", mastery=75)
        db_session.add_all([node1, node2])
        await db_session.flush()

        # 创建不同类型的边
        edge_tree = Edge(
            space_id=test_space.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            type=EdgeType.KNOWLEDGE_TREE,
        )
        edge_advanced = Edge(
            space_id=test_space.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            type=EdgeType.ADVANCED,
        )
        db_session.add_all([edge_tree, edge_advanced])
        await db_session.commit()

        result = await db_session.execute(
            select(Edge).where(Edge.space_id == test_space.id)
        )
        edges = result.scalars().all()

        assert len(edges) == 2
        edge_types = {e.type for e in edges}
        assert EdgeType.KNOWLEDGE_TREE in edge_types
        assert EdgeType.ADVANCED in edge_types


class TestCascadeDeleteOnSpace:
    """空间删除级联测试"""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """创建测试用户"""
        user = User(
            id=uuid4(),
            email="cascade@test.com",
            nickname="Cascade User",
        )
        db_session.add(user)
        await db_session.commit()
        return user

    @pytest.mark.asyncio
    async def test_delete_space_deletes_nodes(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试删除空间同时删除节点"""
        space = Space(
            id=uuid4(),
            user_id=test_user.id,
            name="Cascade Space",
            color="#AABBCC",
        )
        db_session.add(space)
        await db_session.flush()

        # 添加节点
        node = Node(space_id=space.id, label="Test Node", mastery=50)
        db_session.add(node)
        await db_session.commit()

        space_id = space.id

        # 删除空间
        await db_session.delete(space)
        await db_session.commit()

        # 验证节点被删除
        result = await db_session.execute(
            select(Node).where(Node.space_id == space_id)
        )
        nodes = result.scalars().all()
        assert len(nodes) == 0

    @pytest.mark.asyncio
    async def test_delete_space_deletes_edges(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试删除空间同时删除边"""
        space = Space(
            id=uuid4(),
            user_id=test_user.id,
            name="Cascade Space",
            color="#DDEEFF",
        )
        db_session.add(space)
        await db_session.flush()

        # 添加节点和边
        node1 = Node(space_id=space.id, label="Node 1", mastery=50)
        node2 = Node(space_id=space.id, label="Node 2", mastery=75)
        db_session.add_all([node1, node2])
        await db_session.flush()

        edge = Edge(
            space_id=space.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            type=EdgeType.KNOWLEDGE_TREE,
        )
        db_session.add(edge)
        await db_session.commit()

        space_id = space.id

        # 删除空间
        await db_session.delete(space)
        await db_session.commit()

        # 验证边被删除
        result = await db_session.execute(
            select(Edge).where(Edge.space_id == space_id)
        )
        edges = result.scalars().all()
        assert len(edges) == 0

    @pytest.mark.asyncio
    async def test_delete_space_deletes_tasks(
        self, db_session: AsyncSession, test_user: User
    ):
        """测试删除空间同时删除任务"""
        space = Space(
            id=uuid4(),
            user_id=test_user.id,
            name="Cascade Task Space",
            color="#112233",
        )
        db_session.add(space)
        await db_session.flush()

        # 添加任务
        task = AgentTask(
            user_id=test_user.id,
            space_id=space.id,
            task_type=AgentTaskType.GENERATE_KNOWLEDGE_GRAPH,
            input_data={"topic": "Test"},
        )
        db_session.add(task)
        await db_session.commit()

        space_id = space.id

        # 删除空间
        await db_session.delete(space)
        await db_session.commit()

        # 验证任务被删除
        result = await db_session.execute(
            select(AgentTask).where(AgentTask.space_id == space_id)
        )
        tasks = result.scalars().all()
        assert len(tasks) == 0


class TestUniqueConstraintOnEdges:
    """边唯一约束测试"""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """创建测试用户"""
        user = User(
            id=uuid4(),
            email="unique@test.com",
            nickname="Unique User",
        )
        db_session.add(user)
        await db_session.commit()
        return user

    @pytest_asyncio.fixture
    async def test_space(self, db_session: AsyncSession, test_user: User) -> Space:
        """创建测试学习空间"""
        space = Space(
            id=uuid4(),
            user_id=test_user.id,
            name="Unique Space",
            color="#445566",
        )
        db_session.add(space)
        await db_session.commit()
        return space

    @pytest.mark.asyncio
    async def test_same_edge_different_types_allowed(
        self, db_session: AsyncSession, test_space: Space
    ):
        """测试相同节点对、不同类型的边是允许的"""
        node1 = Node(space_id=test_space.id, label="A", mastery=50)
        node2 = Node(space_id=test_space.id, label="B", mastery=75)
        db_session.add_all([node1, node2])
        await db_session.flush()

        # 相同节点对，不同类型
        edge1 = Edge(
            space_id=test_space.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            type=EdgeType.KNOWLEDGE_TREE,
        )
        edge2 = Edge(
            space_id=test_space.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            type=EdgeType.ADVANCED,
        )
        db_session.add_all([edge1, edge2])
        await db_session.commit()

        result = await db_session.execute(
            select(Edge).where(Edge.space_id == test_space.id)
        )
        edges = result.scalars().all()
        assert len(edges) == 2


class TestNodeMasteryConstraint:
    """节点掌握度约束测试"""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """创建测试用户"""
        user = User(
            id=uuid4(),
            email="mastery@test.com",
            nickname="Mastery User",
        )
        db_session.add(user)
        await db_session.commit()
        return user

    @pytest_asyncio.fixture
    async def test_space(self, db_session: AsyncSession, test_user: User) -> Space:
        """创建测试学习空间"""
        space = Space(
            id=uuid4(),
            user_id=test_user.id,
            name="Mastery Space",
            color="#778899",
        )
        db_session.add(space)
        await db_session.commit()
        return space

    @pytest.mark.asyncio
    async def test_mastery_zero_allowed(
        self, db_session: AsyncSession, test_space: Space
    ):
        """测试掌握度为 0 是允许的"""
        node = Node(space_id=test_space.id, label="Zero", mastery=0)
        db_session.add(node)
        await db_session.commit()

        assert node.mastery == 0

    @pytest.mark.asyncio
    async def test_mastery_100_allowed(
        self, db_session: AsyncSession, test_space: Space
    ):
        """测试掌握度为 100 是允许的"""
        node = Node(space_id=test_space.id, label="Full", mastery=100)
        db_session.add(node)
        await db_session.commit()

        assert node.mastery == 100

    @pytest.mark.asyncio
    async def test_mastery_null_allowed(
        self, db_session: AsyncSession, test_space: Space
    ):
        """测试掌握度为 NULL 是允许的"""
        node = Node(space_id=test_space.id, label="Unknown", mastery=None)
        db_session.add(node)
        await db_session.commit()

        assert node.mastery is None
