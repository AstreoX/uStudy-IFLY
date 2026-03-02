"""Graph 测试专用 fixtures"""

from uuid import uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Node, Edge, EdgeType, Space, User


@pytest_asyncio.fixture
async def graph_test_user(db_session: AsyncSession) -> User:
    """创建图谱测试用户"""
    user = User(
        id=uuid4(),
        email="graph_test@test.com",
        nickname="Graph Test User",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def graph_test_space(db_session: AsyncSession, graph_test_user: User) -> Space:
    """创建图谱测试学习空间"""
    space = Space(
        id=uuid4(),
        user_id=graph_test_user.id,
        name="Graph Test Space",
        color="#00FF00",
    )
    db_session.add(space)
    await db_session.commit()
    return space


@pytest_asyncio.fixture
async def sample_graph(db_session: AsyncSession, graph_test_space: Space) -> dict:
    """
    创建示例知识图谱结构：

    数据结构 (root)
    ├── 线性结构
    │   ├── 数组
    │   └── 链表
    └── 非线性结构
        ├── 树
        └── 图
    """
    space_id = graph_test_space.id

    # 创建节点
    root = Node(id=uuid4(), space_id=space_id, label="数据结构", mastery=50)
    linear = Node(id=uuid4(), space_id=space_id, label="线性结构", mastery=60)
    nonlinear = Node(id=uuid4(), space_id=space_id, label="非线性结构", mastery=40)
    array = Node(id=uuid4(), space_id=space_id, label="数组", mastery=80)
    linked_list = Node(id=uuid4(), space_id=space_id, label="链表", mastery=70)
    tree = Node(id=uuid4(), space_id=space_id, label="树", mastery=30)
    graph_node = Node(id=uuid4(), space_id=space_id, label="图", mastery=20)

    nodes = [root, linear, nonlinear, array, linked_list, tree, graph_node]
    for node in nodes:
        db_session.add(node)

    # 创建树形边
    edges = [
        Edge(id=uuid4(), space_id=space_id, from_node_id=root.id, to_node_id=linear.id, type=EdgeType.KNOWLEDGE_TREE),
        Edge(id=uuid4(), space_id=space_id, from_node_id=root.id, to_node_id=nonlinear.id, type=EdgeType.KNOWLEDGE_TREE),
        Edge(id=uuid4(), space_id=space_id, from_node_id=linear.id, to_node_id=array.id, type=EdgeType.KNOWLEDGE_TREE),
        Edge(id=uuid4(), space_id=space_id, from_node_id=linear.id, to_node_id=linked_list.id, type=EdgeType.KNOWLEDGE_TREE),
        Edge(id=uuid4(), space_id=space_id, from_node_id=nonlinear.id, to_node_id=tree.id, type=EdgeType.KNOWLEDGE_TREE),
        Edge(id=uuid4(), space_id=space_id, from_node_id=nonlinear.id, to_node_id=graph_node.id, type=EdgeType.KNOWLEDGE_TREE),
    ]
    for edge in edges:
        db_session.add(edge)

    await db_session.commit()

    return {
        "space": graph_test_space,
        "nodes": {
            "root": root,
            "linear": linear,
            "nonlinear": nonlinear,
            "array": array,
            "linked_list": linked_list,
            "tree": tree,
            "graph": graph_node,
        },
        "edges": edges,
    }


@pytest_asyncio.fixture
async def empty_graph_space(db_session: AsyncSession, graph_test_user: User) -> Space:
    """创建空的图谱学习空间"""
    space = Space(
        id=uuid4(),
        user_id=graph_test_user.id,
        name="Empty Graph Space",
        color="#0000FF",
    )
    db_session.add(space)
    await db_session.commit()
    return space


@pytest_asyncio.fixture
async def circular_graph(db_session: AsyncSession, graph_test_space: Space) -> dict:
    """
    创建包含循环引用的图：
    A -> B -> C -> A (循环)
    """
    space_id = graph_test_space.id

    node_a = Node(id=uuid4(), space_id=space_id, label="节点A", mastery=50)
    node_b = Node(id=uuid4(), space_id=space_id, label="节点B", mastery=60)
    node_c = Node(id=uuid4(), space_id=space_id, label="节点C", mastery=70)

    for node in [node_a, node_b, node_c]:
        db_session.add(node)

    edges = [
        Edge(id=uuid4(), space_id=space_id, from_node_id=node_a.id, to_node_id=node_b.id, type=EdgeType.ADVANCED),
        Edge(id=uuid4(), space_id=space_id, from_node_id=node_b.id, to_node_id=node_c.id, type=EdgeType.ADVANCED),
        Edge(id=uuid4(), space_id=space_id, from_node_id=node_c.id, to_node_id=node_a.id, type=EdgeType.ADVANCED),
    ]
    for edge in edges:
        db_session.add(edge)

    await db_session.commit()

    return {
        "space": graph_test_space,
        "nodes": {"a": node_a, "b": node_b, "c": node_c},
        "edges": edges,
    }
