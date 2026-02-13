"""知识图谱 Agent 单元测试"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.exceptions import LLMClientError, LLMParsingError, SpaceNotFoundError
from agents.knowledge_graph_agent import KnowledgeGraphAgent
from agents.parsers.knowledge_graph import ParsedEdge, ParsedKnowledgeGraph, ParsedNode
from agents.schemas import KnowledgeGraphGenerateRequest
from db.models import Edge, EdgeType, Node, Space, User


class TestKnowledgeGraphAgentInit:
    """Agent 初始化测试"""

    @pytest.mark.asyncio
    async def test_init_creates_components(self, db_session: AsyncSession):
        """测试 Agent 初始化创建必要组件"""
        with patch("agents.knowledge_graph_agent.OpenRouterClient") as mock_client:
            mock_client.return_value = MagicMock()
            agent = KnowledgeGraphAgent(db_session)

            assert agent.db == db_session
            assert agent.llm_client is not None
            assert agent.parser is not None


class TestKnowledgeGraphAgentGenerate:
    """Agent 生成流程测试"""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """创建测试用户"""
        user = User(
            id=uuid4(),
            email="test@example.com",
            nickname="Test User",
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
            name="Test Space",
            color="#FF0000",
        )
        db_session.add(space)
        await db_session.commit()
        return space

    @pytest_asyncio.fixture
    def mock_llm_response(self) -> str:
        """模拟 LLM 响应"""
        return """
<knowledge_graph>
/basic_knowledge_tree
* Topic A [0.5]
** Sub A1 [0.3]
** Sub A2 [0.7]

/advanced_knowledge_connections
Sub A1->Sub A2
</knowledge_graph>
"""

    @pytest.mark.asyncio
    async def test_generate_success(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
        mock_llm_response: str,
    ):
        """测试完整成功流程"""
        with patch("agents.knowledge_graph_agent.OpenRouterClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.complete = AsyncMock(return_value=mock_llm_response)
            mock_client_cls.return_value = mock_client

            agent = KnowledgeGraphAgent(db_session)
            request = KnowledgeGraphGenerateRequest(topic="Test Topic")

            space_id, node_count, edge_count = await agent.generate(
                user_id=test_user.id,
                space_id=test_space.id,
                request=request,
            )

            assert space_id == test_space.id
            assert node_count == 3  # Topic A, Sub A1, Sub A2
            assert edge_count == 3  # 2 tree edges + 1 advanced

            # 验证数据库中的节点
            result = await db_session.execute(
                select(Node).where(Node.space_id == test_space.id)
            )
            nodes = result.scalars().all()
            assert len(nodes) == 3

            # 验证数据库中的边
            result = await db_session.execute(
                select(Edge).where(Edge.space_id == test_space.id)
            )
            edges = result.scalars().all()
            assert len(edges) == 3

    @pytest.mark.asyncio
    async def test_space_not_found(self, db_session: AsyncSession, test_user: User):
        """测试空间不存在"""
        with patch("agents.knowledge_graph_agent.OpenRouterClient") as mock_client_cls:
            mock_client_cls.return_value = MagicMock()

            agent = KnowledgeGraphAgent(db_session)
            request = KnowledgeGraphGenerateRequest(topic="Test Topic")

            with pytest.raises(SpaceNotFoundError, match="学习空间不存在"):
                await agent.generate(
                    user_id=test_user.id,
                    space_id=uuid4(),  # 不存在的空间
                    request=request,
                )

    @pytest.mark.asyncio
    async def test_space_belongs_to_other_user(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试空间属于其他用户"""
        with patch("agents.knowledge_graph_agent.OpenRouterClient") as mock_client_cls:
            mock_client_cls.return_value = MagicMock()

            agent = KnowledgeGraphAgent(db_session)
            request = KnowledgeGraphGenerateRequest(topic="Test Topic")

            # 使用不同的用户 ID
            other_user_id = uuid4()

            with pytest.raises(SpaceNotFoundError):
                await agent.generate(
                    user_id=other_user_id,
                    space_id=test_space.id,
                    request=request,
                )

    @pytest.mark.asyncio
    async def test_llm_call_failure(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试 LLM 调用失败"""
        with patch("agents.knowledge_graph_agent.OpenRouterClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.complete = AsyncMock(
                side_effect=httpx.TimeoutException("Connection timeout")
            )
            mock_client_cls.return_value = mock_client

            agent = KnowledgeGraphAgent(db_session)
            request = KnowledgeGraphGenerateRequest(topic="Test Topic")

            with pytest.raises(LLMClientError):
                await agent.generate(
                    user_id=test_user.id,
                    space_id=test_space.id,
                    request=request,
                )

    @pytest.mark.asyncio
    async def test_parsing_failure_after_retries(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试解析失败（重试后仍失败）"""
        invalid_response = "Invalid LLM output without proper tags"

        with patch("agents.knowledge_graph_agent.OpenRouterClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.complete = AsyncMock(return_value=invalid_response)
            mock_client_cls.return_value = mock_client

            agent = KnowledgeGraphAgent(db_session)
            request = KnowledgeGraphGenerateRequest(topic="Test Topic")

            with pytest.raises(LLMParsingError):
                await agent.generate(
                    user_id=test_user.id,
                    space_id=test_space.id,
                    request=request,
                )

    @pytest.mark.asyncio
    async def test_retry_on_parse_failure_then_success(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
        mock_llm_response: str,
    ):
        """测试解析失败后重试成功"""
        invalid_response = "Invalid"
        call_count = 0

        async def mock_complete(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return invalid_response
            return mock_llm_response

        with patch("agents.knowledge_graph_agent.OpenRouterClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.complete = mock_complete
            mock_client_cls.return_value = mock_client

            agent = KnowledgeGraphAgent(db_session)
            request = KnowledgeGraphGenerateRequest(topic="Test Topic")

            space_id, node_count, edge_count = await agent.generate(
                user_id=test_user.id,
                space_id=test_space.id,
                request=request,
            )

            assert call_count == 2
            assert node_count == 3


class TestKnowledgeGraphAgentPersistence:
    """数据持久化测试"""

    @pytest_asyncio.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """创建测试用户"""
        user = User(
            id=uuid4(),
            email="persist@example.com",
            nickname="Persist User",
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
            name="Persist Space",
            color="#00FF00",
        )
        db_session.add(space)
        await db_session.commit()
        return space

    @pytest.mark.asyncio
    async def test_nodes_persisted_correctly(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试节点正确保存"""
        llm_response = """
<knowledge_graph>
/basic_knowledge_tree
* Root [0.8]
** Child A [0.5]
** Child B [-1]

/advanced_knowledge_connections
</knowledge_graph>
"""
        with patch("agents.knowledge_graph_agent.OpenRouterClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.complete = AsyncMock(return_value=llm_response)
            mock_client_cls.return_value = mock_client

            agent = KnowledgeGraphAgent(db_session)
            request = KnowledgeGraphGenerateRequest(topic="Test")

            await agent.generate(
                user_id=test_user.id,
                space_id=test_space.id,
                request=request,
            )

            # 查询节点
            result = await db_session.execute(
                select(Node).where(Node.space_id == test_space.id)
            )
            nodes = {n.label: n for n in result.scalars().all()}

            # 验证掌握度
            assert nodes["Root"].mastery == 80
            assert nodes["Child A"].mastery == 50
            assert nodes["Child B"].mastery is None  # -1 转换为 None

    @pytest.mark.asyncio
    async def test_edges_persisted_correctly(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_space: Space,
    ):
        """测试边正确保存"""
        llm_response = """
<knowledge_graph>
/basic_knowledge_tree
* Root [0.5]
** Child [0.3]

/advanced_knowledge_connections
Root->Child
</knowledge_graph>
"""
        with patch("agents.knowledge_graph_agent.OpenRouterClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.complete = AsyncMock(return_value=llm_response)
            mock_client_cls.return_value = mock_client

            agent = KnowledgeGraphAgent(db_session)
            request = KnowledgeGraphGenerateRequest(topic="Test")

            await agent.generate(
                user_id=test_user.id,
                space_id=test_space.id,
                request=request,
            )

            # 查询边
            result = await db_session.execute(
                select(Edge).where(Edge.space_id == test_space.id)
            )
            edges = result.scalars().all()

            # 应该有 2 条边：1 个树边 + 1 个高级连接
            assert len(edges) == 2

            # 验证边类型
            edge_types = {e.type for e in edges}
            assert EdgeType.KNOWLEDGE_TREE in edge_types
            assert EdgeType.ADVANCED in edge_types


class TestEdgeTypeMapping:
    """边类型映射测试"""

    @pytest.mark.asyncio
    async def test_map_edge_type_knowledge_tree(self, db_session: AsyncSession):
        """测试映射 knowledge_tree 类型"""
        with patch("agents.knowledge_graph_agent.OpenRouterClient") as mock_client_cls:
            mock_client_cls.return_value = MagicMock()
            agent = KnowledgeGraphAgent(db_session)

            result = agent._map_edge_type("knowledge_tree")
            assert result == EdgeType.KNOWLEDGE_TREE

    @pytest.mark.asyncio
    async def test_map_edge_type_advanced(self, db_session: AsyncSession):
        """测试映射 advanced 类型"""
        with patch("agents.knowledge_graph_agent.OpenRouterClient") as mock_client_cls:
            mock_client_cls.return_value = MagicMock()
            agent = KnowledgeGraphAgent(db_session)

            result = agent._map_edge_type("advanced")
            assert result == EdgeType.ADVANCED

    @pytest.mark.asyncio
    async def test_map_edge_type_unknown_defaults_to_tree(
        self, db_session: AsyncSession
    ):
        """测试未知类型默认为 KNOWLEDGE_TREE"""
        with patch("agents.knowledge_graph_agent.OpenRouterClient") as mock_client_cls:
            mock_client_cls.return_value = MagicMock()
            agent = KnowledgeGraphAgent(db_session)

            result = agent._map_edge_type("unknown_type")
            assert result == EdgeType.KNOWLEDGE_TREE


class TestInputValidation:
    """输入验证测试"""

    def test_topic_required(self):
        """测试主题必填"""
        with pytest.raises(ValueError):
            KnowledgeGraphGenerateRequest(topic="")

    def test_topic_max_length(self):
        """测试主题长度限制"""
        long_topic = "a" * 501
        with pytest.raises(ValueError):
            KnowledgeGraphGenerateRequest(topic=long_topic)

    def test_topic_valid_length(self):
        """测试有效的主题长度"""
        request = KnowledgeGraphGenerateRequest(topic="Valid Topic")
        assert request.topic == "Valid Topic"

    def test_user_preference_optional(self):
        """测试用户偏好可选"""
        request = KnowledgeGraphGenerateRequest(topic="Topic")
        assert request.user_preference is None

    def test_user_preference_with_value(self):
        """测试带用户偏好"""
        request = KnowledgeGraphGenerateRequest(
            topic="Topic",
            user_preference="Prefer visual content",
        )
        assert request.user_preference == "Prefer visual content"

    def test_user_preference_max_length(self):
        """测试用户偏好长度限制"""
        long_preference = "a" * 1001
        with pytest.raises(ValueError):
            KnowledgeGraphGenerateRequest(
                topic="Topic",
                user_preference=long_preference,
            )
