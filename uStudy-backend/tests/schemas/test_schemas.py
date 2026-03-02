"""Pydantic Schema 测试"""

from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from db.models import EdgeType, MessageRole, SubscriptionTier
from schemas.user import UserCreate, UserResponse, UserUpdate
from schemas.space import SpaceCreate, SpaceResponse, SpaceUpdate
from schemas.conversation import ConversationCreate, ConversationResponse
from schemas.message import MessageCreate, MessageResponse
from schemas.node import NodeCreate, NodeResponse, NodeUpdate
from schemas.edge import EdgeCreate, EdgeResponse


# ============ User Schema 测试 ============


class TestUserSchema:
    """User Schema 测试"""

    def test_user_create_validates_email(self):
        """邮箱格式验证"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                email="invalid_email",
                nickname="Test",
                password="password123",
            )
        assert "email" in str(exc_info.value)

    def test_user_create_valid(self):
        """有效用户创建"""
        user = UserCreate(
            email="test@example.com",
            nickname="Test User",
            password="secure_password",
        )
        assert user.email == "test@example.com"
        assert user.nickname == "Test User"

    def test_user_create_password_min_length(self):
        """密码最小长度验证"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                email="test@example.com",
                nickname="Test",
                password="12345",  # 少于 6 位
            )
        assert "password" in str(exc_info.value)

    def test_user_response_from_model(self):
        """Model 转 Response"""
        # 模拟 ORM 对象的字典
        user_data = {
            "id": uuid4(),
            "email": "user@example.com",
            "nickname": "User",
            "subscription_tier": SubscriptionTier.FREE,
            "created_at": datetime.now(),
        }
        user = UserResponse.model_validate(user_data)
        assert user.email == "user@example.com"
        assert user.subscription_tier == SubscriptionTier.FREE

    def test_user_update_partial(self):
        """用户部分更新"""
        update = UserUpdate(nickname="New Name")
        assert update.nickname == "New Name"
        assert update.password is None


# ============ Space Schema 测试 ============


class TestSpaceSchema:
    """Space Schema 测试"""

    def test_space_create_valid(self):
        """有效空间创建"""
        space = SpaceCreate(
            name="My Space",
            description="A learning space",
            color="#FF5733",
        )
        assert space.name == "My Space"
        assert space.color == "#FF5733"

    def test_space_create_invalid_color(self):
        """无效颜色格式"""
        with pytest.raises(ValidationError) as exc_info:
            SpaceCreate(
                name="Space",
                color="red",  # 无效格式
            )
        assert "color" in str(exc_info.value)

    def test_space_create_valid_color_formats(self):
        """有效颜色格式"""
        # 大写
        space1 = SpaceCreate(name="Space", color="#AABBCC")
        assert space1.color == "#AABBCC"

        # 小写
        space2 = SpaceCreate(name="Space", color="#aabbcc")
        assert space2.color == "#aabbcc"

    def test_space_update_partial(self):
        """空间部分更新"""
        update = SpaceUpdate(name="Updated Name")
        assert update.name == "Updated Name"
        assert update.color is None

    def test_space_response_from_dict(self):
        """Space Response 创建"""
        space_data = {
            "id": uuid4(),
            "user_id": uuid4(),
            "name": "Test Space",
            "description": None,
            "color": "#000000",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        space = SpaceResponse.model_validate(space_data)
        assert space.name == "Test Space"


# ============ Conversation Schema 测试 ============


class TestConversationSchema:
    """Conversation Schema 测试"""

    def test_conversation_create_with_space(self):
        """创建绑定空间的对话"""
        space_id = uuid4()
        conv = ConversationCreate(
            title="Math Discussion",
            space_id=space_id,
        )
        assert conv.title == "Math Discussion"
        assert conv.space_id == space_id

    def test_conversation_create_without_space(self):
        """创建快速对话"""
        conv = ConversationCreate(title="Quick Chat")
        assert conv.space_id is None


# ============ Message Schema 测试 ============


class TestMessageSchema:
    """Message Schema 测试"""

    def test_message_create_user_role(self):
        """用户消息创建"""
        msg = MessageCreate(
            role=MessageRole.USER,
            content="Hello!",
        )
        assert msg.role == MessageRole.USER

    def test_message_create_assistant_role(self):
        """AI 消息创建"""
        msg = MessageCreate(
            role=MessageRole.ASSISTANT,
            content="Hi there!",
        )
        assert msg.role == MessageRole.ASSISTANT

    def test_message_create_empty_content(self):
        """空内容验证"""
        with pytest.raises(ValidationError) as exc_info:
            MessageCreate(
                role=MessageRole.USER,
                content="",  # 空内容
            )
        assert "content" in str(exc_info.value)


# ============ Node Schema 测试 ============


class TestNodeSchema:
    """Node Schema 测试"""

    def test_node_create_default_mastery(self):
        """默认 mastery=0"""
        node = NodeCreate(label="Algebra")
        assert node.mastery == 0

    def test_node_create_with_mastery(self):
        """指定 mastery"""
        node = NodeCreate(label="Calculus", mastery=50)
        assert node.mastery == 50

    def test_node_mastery_range_min(self):
        """mastery 最小值验证"""
        with pytest.raises(ValidationError) as exc_info:
            NodeCreate(label="Node", mastery=-1)
        assert "mastery" in str(exc_info.value)

    def test_node_mastery_range_max(self):
        """mastery 最大值验证"""
        with pytest.raises(ValidationError) as exc_info:
            NodeCreate(label="Node", mastery=101)
        assert "mastery" in str(exc_info.value)

    def test_node_update_partial(self):
        """节点部分更新"""
        update = NodeUpdate(mastery=75)
        assert update.mastery == 75
        assert update.label is None


# ============ Edge Schema 测试 ============


class TestEdgeSchema:
    """Edge Schema 测试"""

    def test_edge_create_knowledge_tree(self):
        """知识树边创建"""
        edge = EdgeCreate(
            from_node_id=uuid4(),
            to_node_id=uuid4(),
            type=EdgeType.KNOWLEDGE_TREE,
        )
        assert edge.type == EdgeType.KNOWLEDGE_TREE

    def test_edge_create_learning_path(self):
        """学习路径边创建"""
        edge = EdgeCreate(
            from_node_id=uuid4(),
            to_node_id=uuid4(),
            type=EdgeType.LEARNING_PATH,
        )
        assert edge.type == EdgeType.LEARNING_PATH

    def test_edge_response_from_dict(self):
        """Edge Response 创建"""
        edge_data = {
            "id": uuid4(),
            "space_id": uuid4(),
            "from_node_id": uuid4(),
            "to_node_id": uuid4(),
            "type": EdgeType.KNOWLEDGE_TREE,
            "created_at": datetime.now(),
        }
        edge = EdgeResponse.model_validate(edge_data)
        assert edge.type == EdgeType.KNOWLEDGE_TREE
