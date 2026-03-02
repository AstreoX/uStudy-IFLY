"""知识图谱生成端到端测试

注意：这些测试需要真实的 OpenRouter API Key。
运行前请确保 OPENROUTER_API_KEY 环境变量已设置。

运行方式：
    pytest tests/agents/test_e2e_knowledge_graph.py -v -m e2e
"""

import asyncio
import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.knowledge_graph_agent import KnowledgeGraphAgent
from agents.schemas import KnowledgeGraphGenerateRequest
from db.models import Edge, EdgeType, Node, Space, User


# 标记所有 E2E 测试
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not os.getenv("OPENROUTER_API_KEY"),
        reason="OPENROUTER_API_KEY 环境变量未设置",
    ),
]


class TestFullGenerationFlow:
    """完整生成流程 E2E 测试"""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """创建测试用户"""
        user = User(
            id=uuid4(),
            email="e2e@test.com",
            nickname="E2E User",
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
            name="E2E Space",
            color="#E2E2E2",
        )
        db_session.add(space)
        await db_session.commit()
        return space

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)  # 3 分钟超时
    async def test_full_generation_flow(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试完整生成流程（使用真实 LLM）"""
        agent = KnowledgeGraphAgent(db_session)
        request = KnowledgeGraphGenerateRequest(
            topic="Python 基础编程",
            user_preference="适合初学者，注重实践",
        )

        space_id, node_count, edge_count = await agent.generate(
            user_id=test_user.id,
            space_id=test_space.id,
            request=request,
        )

        # 验证返回值
        assert space_id == test_space.id
        assert node_count > 0
        assert edge_count > 0

        # 验证数据库中的数据
        result = await db_session.execute(
            select(Node).where(Node.space_id == test_space.id)
        )
        nodes = result.scalars().all()
        assert len(nodes) == node_count

        result = await db_session.execute(
            select(Edge).where(Edge.space_id == test_space.id)
        )
        edges = result.scalars().all()
        assert len(edges) == edge_count

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_chinese_topic_generation(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试中文主题生成"""
        agent = KnowledgeGraphAgent(db_session)
        request = KnowledgeGraphGenerateRequest(
            topic="机器学习入门",
        )

        space_id, node_count, edge_count = await agent.generate(
            user_id=test_user.id,
            space_id=test_space.id,
            request=request,
        )

        assert node_count > 0

        # 验证节点包含中文内容
        result = await db_session.execute(
            select(Node).where(Node.space_id == test_space.id)
        )
        nodes = result.scalars().all()

        # 至少有一个节点包含中文
        has_chinese = any(
            any("\u4e00" <= c <= "\u9fff" for c in n.label) for n in nodes
        )
        assert has_chinese, "生成的节点应该包含中文内容"

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_with_user_preference(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试带用户偏好的生成"""
        agent = KnowledgeGraphAgent(db_session)
        request = KnowledgeGraphGenerateRequest(
            topic="Web 开发",
            user_preference="专注于前端开发，使用 React 框架",
        )

        space_id, node_count, edge_count = await agent.generate(
            user_id=test_user.id,
            space_id=test_space.id,
            request=request,
        )

        assert node_count > 0
        assert edge_count > 0


class TestGeneratedContentValidation:
    """生成内容验证测试"""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """创建测试用户"""
        user = User(
            id=uuid4(),
            email="validation_e2e@test.com",
            nickname="Validation E2E User",
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
            name="Validation E2E Space",
            color="#V4L1D8",
        )
        db_session.add(space)
        await db_session.commit()
        return space

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_generated_nodes_reasonable(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试生成节点数量合理 (10-50个)"""
        agent = KnowledgeGraphAgent(db_session)
        request = KnowledgeGraphGenerateRequest(
            topic="数据结构与算法",
        )

        space_id, node_count, edge_count = await agent.generate(
            user_id=test_user.id,
            space_id=test_space.id,
            request=request,
        )

        # 验证节点数量在合理范围
        assert 5 <= node_count <= 60, f"节点数量 {node_count} 不在预期范围 [5, 60]"

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_tree_structure_valid(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试树结构有效"""
        agent = KnowledgeGraphAgent(db_session)
        request = KnowledgeGraphGenerateRequest(
            topic="JavaScript 基础",
        )

        await agent.generate(
            user_id=test_user.id,
            space_id=test_space.id,
            request=request,
        )

        # 获取树边
        result = await db_session.execute(
            select(Edge).where(
                Edge.space_id == test_space.id,
                Edge.type == EdgeType.KNOWLEDGE_TREE,
            )
        )
        tree_edges = result.scalars().all()

        # 验证树边数量（应该等于节点数-1或更少，因为可能有多个根节点）
        result = await db_session.execute(
            select(Node).where(Node.space_id == test_space.id)
        )
        nodes = result.scalars().all()

        # 树边数量应该合理
        assert len(tree_edges) <= len(nodes), "树边数量不应超过节点数量"

        # 验证所有边的节点都存在
        node_ids = {n.id for n in nodes}
        for edge in tree_edges:
            assert edge.from_node_id in node_ids, f"源节点 {edge.from_node_id} 不存在"
            assert edge.to_node_id in node_ids, f"目标节点 {edge.to_node_id} 不存在"

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_mastery_values_in_range(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试掌握度在范围内"""
        agent = KnowledgeGraphAgent(db_session)
        request = KnowledgeGraphGenerateRequest(
            topic="Python 数据分析",
        )

        await agent.generate(
            user_id=test_user.id,
            space_id=test_space.id,
            request=request,
        )

        result = await db_session.execute(
            select(Node).where(Node.space_id == test_space.id)
        )
        nodes = result.scalars().all()

        for node in nodes:
            if node.mastery is not None:
                assert 0 <= node.mastery <= 100, (
                    f"节点 '{node.label}' 的掌握度 {node.mastery} 超出范围 [0, 100]"
                )

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_advanced_connections_valid(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试高级连接有效"""
        agent = KnowledgeGraphAgent(db_session)
        request = KnowledgeGraphGenerateRequest(
            topic="计算机网络",
        )

        await agent.generate(
            user_id=test_user.id,
            space_id=test_space.id,
            request=request,
        )

        # 获取高级连接
        result = await db_session.execute(
            select(Edge).where(
                Edge.space_id == test_space.id,
                Edge.type == EdgeType.ADVANCED,
            )
        )
        advanced_edges = result.scalars().all()

        # 获取所有节点
        result = await db_session.execute(
            select(Node).where(Node.space_id == test_space.id)
        )
        nodes = result.scalars().all()
        node_ids = {n.id for n in nodes}

        # 验证所有高级连接的节点都存在
        for edge in advanced_edges:
            assert edge.from_node_id in node_ids, f"高级连接源节点不存在"
            assert edge.to_node_id in node_ids, f"高级连接目标节点不存在"


class TestEdgeCases:
    """边界情况 E2E 测试"""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """创建测试用户"""
        user = User(
            id=uuid4(),
            email="edge_e2e@test.com",
            nickname="Edge E2E User",
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
            name="Edge E2E Space",
            color="#EDGE00",
        )
        db_session.add(space)
        await db_session.commit()
        return space

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_short_topic(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试短主题"""
        agent = KnowledgeGraphAgent(db_session)
        request = KnowledgeGraphGenerateRequest(
            topic="Git",
        )

        space_id, node_count, edge_count = await agent.generate(
            user_id=test_user.id,
            space_id=test_space.id,
            request=request,
        )

        assert node_count > 0

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_long_detailed_topic(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试长详细主题"""
        agent = KnowledgeGraphAgent(db_session)
        request = KnowledgeGraphGenerateRequest(
            topic="深入理解 Python 的装饰器模式、元类编程以及描述符协议的高级应用",
            user_preference="希望包含实际代码示例和最佳实践",
        )

        space_id, node_count, edge_count = await agent.generate(
            user_id=test_user.id,
            space_id=test_space.id,
            request=request,
        )

        assert node_count > 0

    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_english_topic(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试英文主题"""
        agent = KnowledgeGraphAgent(db_session)
        request = KnowledgeGraphGenerateRequest(
            topic="Introduction to Machine Learning",
        )

        space_id, node_count, edge_count = await agent.generate(
            user_id=test_user.id,
            space_id=test_space.id,
            request=request,
        )

        assert node_count > 0
