"""数据库模型测试"""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Conversation,
    Edge,
    EdgeType,
    Message,
    MessageRole,
    Node,
    Space,
    SubscriptionTier,
    User,
)


# ============ User 测试 ============


class TestUserModel:
    """User 模型测试"""

    @pytest.mark.asyncio
    async def test_create_user_with_valid_data(self, db_session: AsyncSession):
        """创建用户成功"""
        user = User(
            email="test@example.com",
            password_hash="hashed_password",
            nickname="Test User",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.nickname == "Test User"
        assert user.created_at is not None
        assert user.updated_at is not None

    @pytest.mark.asyncio
    async def test_user_subscription_default_free(self, db_session: AsyncSession):
        """默认订阅等级为 FREE"""
        user = User(
            email="free@example.com",
            nickname="Free User",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.subscription_tier == SubscriptionTier.FREE

    @pytest.mark.asyncio
    async def test_user_email_unique_constraint(self, db_session: AsyncSession):
        """重复邮箱抛出 IntegrityError"""
        user1 = User(
            email="duplicate@example.com",
            nickname="User 1",
        )
        db_session.add(user1)
        await db_session.commit()

        user2 = User(
            email="duplicate@example.com",
            nickname="User 2",
        )
        db_session.add(user2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_user_with_apple_id(self, db_session: AsyncSession):
        """Apple ID 登录用户"""
        user = User(
            email="apple@example.com",
            apple_id="apple_user_id_123",
            nickname="Apple User",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.apple_id == "apple_user_id_123"
        assert user.password_hash is None


# ============ Space 测试 ============


class TestSpaceModel:
    """Space 模型测试"""

    @pytest.mark.asyncio
    async def test_create_space_with_user(self, db_session: AsyncSession):
        """创建空间成功"""
        user = User(email="user@example.com", nickname="User")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        space = Space(
            user_id=user.id,
            name="Math Study",
            description="Mathematics learning space",
            color="#FF5733",
        )
        db_session.add(space)
        await db_session.commit()
        await db_session.refresh(space)

        assert space.id is not None
        assert space.name == "Math Study"
        assert space.user_id == user.id

    @pytest.mark.asyncio
    async def test_space_belongs_to_user(self, db_session: AsyncSession):
        """空间关联用户"""
        user = User(email="owner@example.com", nickname="Owner")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        space = Space(user_id=user.id, name="My Space", color="#000000")
        db_session.add(space)
        await db_session.commit()

        # 查询并验证关系
        result = await db_session.execute(
            select(Space).where(Space.user_id == user.id)
        )
        fetched_space = result.scalar_one()
        assert fetched_space.name == "My Space"

    @pytest.mark.asyncio
    async def test_user_cascade_deletes_spaces(self, db_session: AsyncSession):
        """删除用户时空间自动删除"""
        user = User(email="delete@example.com", nickname="To Delete")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        space = Space(user_id=user.id, name="Will Be Deleted", color="#FF0000")
        db_session.add(space)
        await db_session.commit()
        space_id = space.id

        # 删除用户
        await db_session.delete(user)
        await db_session.commit()

        # 验证空间也被删除
        result = await db_session.execute(select(Space).where(Space.id == space_id))
        assert result.scalar_one_or_none() is None


# ============ Conversation 测试 ============


class TestConversationModel:
    """Conversation 模型测试"""

    @pytest.mark.asyncio
    async def test_create_conversation_with_space(self, db_session: AsyncSession):
        """创建绑定空间的对话"""
        user = User(email="conv@example.com", nickname="Conv User")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        space = Space(user_id=user.id, name="Study Space", color="#00FF00")
        db_session.add(space)
        await db_session.commit()
        await db_session.refresh(space)

        conversation = Conversation(
            user_id=user.id,
            space_id=space.id,
            title="Math Discussion",
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        assert conversation.space_id == space.id

    @pytest.mark.asyncio
    async def test_create_conversation_without_space(self, db_session: AsyncSession):
        """创建快速对话（不绑定空间）"""
        user = User(email="quick@example.com", nickname="Quick User")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        conversation = Conversation(
            user_id=user.id,
            space_id=None,
            title="Quick Chat",
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        assert conversation.space_id is None


# ============ Message 测试 ============


class TestMessageModel:
    """Message 模型测试"""

    @pytest.mark.asyncio
    async def test_create_message_user_role(self, db_session: AsyncSession):
        """创建用户消息"""
        user = User(email="msg@example.com", nickname="Msg User")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        conversation = Conversation(user_id=user.id, title="Test Conv")
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        message = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="Hello, AI!",
        )
        db_session.add(message)
        await db_session.commit()
        await db_session.refresh(message)

        assert message.role == MessageRole.USER
        assert message.content == "Hello, AI!"

    @pytest.mark.asyncio
    async def test_create_message_assistant_role(self, db_session: AsyncSession):
        """创建 AI 消息"""
        user = User(email="ai@example.com", nickname="AI User")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        conversation = Conversation(user_id=user.id, title="AI Conv")
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        message = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content="Hello! How can I help you?",
        )
        db_session.add(message)
        await db_session.commit()
        await db_session.refresh(message)

        assert message.role == MessageRole.ASSISTANT

    @pytest.mark.asyncio
    async def test_conversation_cascade_deletes_messages(
        self, db_session: AsyncSession
    ):
        """删除对话时消息自动删除"""
        user = User(email="cascade@example.com", nickname="Cascade User")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        conversation = Conversation(user_id=user.id, title="To Delete Conv")
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)

        message = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="Will be deleted",
        )
        db_session.add(message)
        await db_session.commit()
        message_id = message.id

        # 删除对话
        await db_session.delete(conversation)
        await db_session.commit()

        # 验证消息也被删除
        result = await db_session.execute(
            select(Message).where(Message.id == message_id)
        )
        assert result.scalar_one_or_none() is None


# ============ Node 测试 ============


class TestNodeModel:
    """Node 模型测试"""

    @pytest.mark.asyncio
    async def test_create_node_default_mastery(self, db_session: AsyncSession):
        """默认 mastery=0"""
        user = User(email="node@example.com", nickname="Node User")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        space = Space(user_id=user.id, name="Graph Space", color="#0000FF")
        db_session.add(space)
        await db_session.commit()
        await db_session.refresh(space)

        node = Node(space_id=space.id, label="Algebra")
        db_session.add(node)
        await db_session.commit()
        await db_session.refresh(node)

        assert node.mastery == 0

    @pytest.mark.asyncio
    async def test_create_node_with_mastery(self, db_session: AsyncSession):
        """创建带有 mastery 的节点"""
        user = User(email="mastery@example.com", nickname="Mastery User")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        space = Space(user_id=user.id, name="Mastery Space", color="#FF00FF")
        db_session.add(space)
        await db_session.commit()
        await db_session.refresh(space)

        node = Node(space_id=space.id, label="Calculus", mastery=75)
        db_session.add(node)
        await db_session.commit()
        await db_session.refresh(node)

        assert node.mastery == 75


# ============ Edge 测试 ============


class TestEdgeModel:
    """Edge 模型测试"""

    @pytest.mark.asyncio
    async def test_create_edge_knowledge_tree(self, db_session: AsyncSession):
        """创建知识树边"""
        user = User(email="edge@example.com", nickname="Edge User")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        space = Space(user_id=user.id, name="Edge Space", color="#FFFF00")
        db_session.add(space)
        await db_session.commit()
        await db_session.refresh(space)

        node1 = Node(space_id=space.id, label="Math")
        node2 = Node(space_id=space.id, label="Algebra")
        db_session.add_all([node1, node2])
        await db_session.commit()
        await db_session.refresh(node1)
        await db_session.refresh(node2)

        edge = Edge(
            space_id=space.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            type=EdgeType.KNOWLEDGE_TREE,
        )
        db_session.add(edge)
        await db_session.commit()
        await db_session.refresh(edge)

        assert edge.type == EdgeType.KNOWLEDGE_TREE

    @pytest.mark.asyncio
    async def test_create_edge_learning_path(self, db_session: AsyncSession):
        """创建学习路径边"""
        user = User(email="path@example.com", nickname="Path User")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        space = Space(user_id=user.id, name="Path Space", color="#00FFFF")
        db_session.add(space)
        await db_session.commit()
        await db_session.refresh(space)

        node1 = Node(space_id=space.id, label="Basics")
        node2 = Node(space_id=space.id, label="Advanced")
        db_session.add_all([node1, node2])
        await db_session.commit()
        await db_session.refresh(node1)
        await db_session.refresh(node2)

        edge = Edge(
            space_id=space.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            type=EdgeType.LEARNING_PATH,
        )
        db_session.add(edge)
        await db_session.commit()
        await db_session.refresh(edge)

        assert edge.type == EdgeType.LEARNING_PATH

    @pytest.mark.asyncio
    async def test_node_cascade_deletes_edges(self, db_session: AsyncSession):
        """删除节点时边自动删除"""
        user = User(email="delnode@example.com", nickname="Del Node User")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        space = Space(user_id=user.id, name="Del Space", color="#FF0000")
        db_session.add(space)
        await db_session.commit()
        await db_session.refresh(space)

        node1 = Node(space_id=space.id, label="Source")
        node2 = Node(space_id=space.id, label="Target")
        db_session.add_all([node1, node2])
        await db_session.commit()
        await db_session.refresh(node1)
        await db_session.refresh(node2)

        edge = Edge(
            space_id=space.id,
            from_node_id=node1.id,
            to_node_id=node2.id,
            type=EdgeType.KNOWLEDGE_TREE,
        )
        db_session.add(edge)
        await db_session.commit()
        edge_id = edge.id

        # 删除源节点
        await db_session.delete(node1)
        await db_session.commit()

        # 验证边也被删除
        result = await db_session.execute(select(Edge).where(Edge.id == edge_id))
        assert result.scalar_one_or_none() is None
