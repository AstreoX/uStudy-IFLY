"""Idempotent initialization for the fixed Data Structures collaborative course."""

from __future__ import annotations

from uuid import UUID, uuid5

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    Edge,
    EdgeType,
    Node,
    Space,
    SpaceMember,
    SpaceMemberRole,
    SubscriptionTier,
    User,
)
from spaces.colors import get_next_color


COURSE_NAMESPACE = UUID("6c56bf7a-7b73-4eb1-9ab2-c741f55d8f9e")
SYSTEM_USER_ID = uuid5(COURSE_NAMESPACE, "system-user")
DEFAULT_SPACE_ID = uuid5(COURSE_NAMESPACE, "data-structures-space")
SYSTEM_USERNAME = "course_system"
SYSTEM_EMAIL = "course-system@experiment.invalid"
DEFAULT_COURSE_LABEL = "数据结构"
ADVISORY_LOCK_KEY = 0x5553544459464C59


RAW_COURSE_KNOWLEDGE_GRAPH = """<knowledge_graph>
/basic_knowledge_tree
* 数据结构基础 [-1]
** 数据结构的基本概念 [-1]
** 逻辑结构与存储结构 [-1]
** 算法与复杂度 [-1]
*** 时间复杂度 [-1]
*** 空间复杂度 [-1]

* 线性表 [-1]
** 顺序表 [-1]
*** 顺序表的基本操作 [-1]
** 链表 [-1]
*** 单链表 [-1]
*** 双链表 [-1]
*** 链表的基本操作 [-1]
** 顺序表与链表的比较 [-1]

* 栈和队列 [-1]
** 栈 [-1]
*** 栈的基本操作 [-1]
*** 栈的应用 [-1]
** 队列 [-1]
*** 队列的基本操作 [-1]
*** 循环队列 [-1]
*** 队列的应用 [-1]

* 串 [-1]
** 串的基本概念 [-1]
** 模式匹配 [-1]
*** 朴素模式匹配 [-1]
*** KMP算法 [-1]

* 树和二叉树 [-1]
** 树的基本概念 [-1]
** 二叉树 [-1]
*** 二叉树的性质 [-1]
*** 二叉树的存储结构 [-1]
** 二叉树的遍历 [-1]
*** 先序遍历 [-1]
*** 中序遍历 [-1]
*** 后序遍历 [-1]
*** 层序遍历 [-1]
** 哈夫曼树 [-1]
*** 哈夫曼树的构造 [-1]
*** 哈夫曼编码 [-1]

* 图 [-1]
** 图的基本概念 [-1]
** 图的存储结构 [-1]
*** 邻接矩阵 [-1]
*** 邻接表 [-1]
** 图的遍历 [-1]
*** 深度优先搜索 [-1]
*** 广度优先搜索 [-1]
** 最小生成树 [-1]
*** Prim算法 [-1]
*** Kruskal算法 [-1]
** 最短路径 [-1]
*** Dijkstra算法 [-1]
*** Floyd算法 [-1]
** 拓扑排序 [-1]

* 查找 [-1]
** 顺序查找 [-1]
** 折半查找 [-1]
** 二叉排序树 [-1]
** 散列查找 [-1]
*** 散列函数 [-1]
*** 冲突处理 [-1]

* 排序 [-1]
** 插入排序 [-1]
*** 直接插入排序 [-1]
** 交换排序 [-1]
*** 冒泡排序 [-1]
*** 快速排序 [-1]
** 选择排序 [-1]
*** 简单选择排序 [-1]
*** 堆排序 [-1]
** 归并排序 [-1]
** 排序算法比较 [-1]

/advanced_knowledge_connections
顺序表->折半查找
链表->栈
链表->队列
栈->深度优先搜索
队列->广度优先搜索
栈->二叉树的遍历
队列->层序遍历
二叉树->二叉排序树
二叉树->堆排序
树和二叉树->哈夫曼树
图的存储结构->图的遍历
深度优先搜索->拓扑排序
广度优先搜索->最短路径
排序算法比较->时间复杂度
排序算法比较->空间复杂度
</knowledge_graph>"""


def node_id(label: str) -> UUID:
    return uuid5(COURSE_NAMESPACE, f"node:{label}")


def edge_id(edge_type: EdgeType, source: str, target: str) -> UUID:
    return uuid5(COURSE_NAMESPACE, f"edge:{edge_type.value}:{source}->{target}")


def _parse_course_definition():
    # Delayed until application startup to avoid importing the agents package
    # while auth.dependencies is still being initialized.
    from agents.parsers.knowledge_graph import KnowledgeGraphParser

    return KnowledgeGraphParser().parse(
        RAW_COURSE_KNOWLEDGE_GRAPH,
        root_label=DEFAULT_COURSE_LABEL,
    )


def validate_course_definition(course_graph) -> None:
    labels = [node.label for node in course_graph.nodes]
    label_set = set(labels)
    tree_connections = [
        edge for edge in course_graph.edges if edge.edge_type == "knowledge_tree"
    ]
    advanced_connections = [
        edge for edge in course_graph.edges if edge.edge_type == "advanced"
    ]
    if len(labels) != 74 or len(label_set) != 74:
        raise ValueError("Parsed Data Structures course must contain 74 unique nodes including its root")
    if labels[0] != DEFAULT_COURSE_LABEL:
        raise ValueError("Parsed Data Structures course must start with its injected root node")
    if len(tree_connections) != 73:
        raise ValueError("Parsed Data Structures course must contain 73 tree edges")
    if len(advanced_connections) != 15:
        raise ValueError("Parsed Data Structures course must contain 15 advanced edges")
    missing = sorted(
        {
            label
            for edge in advanced_connections
            for label in (edge.source_label, edge.target_label)
            if label not in label_set
        }
    )
    if missing:
        raise ValueError(f"Advanced connections reference missing nodes: {missing}")


async def _acquire_seed_lock(db: AsyncSession) -> None:
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": ADVISORY_LOCK_KEY},
        )


async def ensure_default_space_membership(db: AsyncSession, user_id: UUID) -> bool:
    """Ensure a real user is a read-only member of the fixed course."""
    if user_id == SYSTEM_USER_ID:
        return True
    space_exists = await db.scalar(select(Space.id).where(Space.id == DEFAULT_SPACE_ID))
    if not space_exists:
        return False
    existing = await db.scalar(
        select(SpaceMember.id).where(
            SpaceMember.space_id == DEFAULT_SPACE_ID,
            SpaceMember.user_id == user_id,
        )
    )
    if existing:
        return True
    member_count = await db.scalar(
        select(func.count()).select_from(SpaceMember).where(
            SpaceMember.space_id == DEFAULT_SPACE_ID
        )
    )
    db.add(
        SpaceMember(
            id=uuid5(COURSE_NAMESPACE, f"member:{user_id}"),
            space_id=DEFAULT_SPACE_ID,
            user_id=user_id,
            role=SpaceMemberRole.MEMBER,
            color=get_next_color(int(member_count or 0)),
            can_edit_graph=False,
        )
    )
    await db.flush()
    return True


async def ensure_default_course(db: AsyncSession) -> None:
    """Parse and idempotently persist the fixed course, then repair missing rows."""
    course_graph = _parse_course_definition()
    validate_course_definition(course_graph)
    await _acquire_seed_lock(db)

    system_user = await db.get(User, SYSTEM_USER_ID)
    if system_user is None:
        db.add(
            User(
                id=SYSTEM_USER_ID,
                username=SYSTEM_USERNAME,
                email=SYSTEM_EMAIL,
                nickname="课程管理员",
                password_hash=None,
                subscription_tier=SubscriptionTier.ALPHA,
                subscription_expires_at=None,
            )
        )
        await db.flush()

    space = await db.get(Space, DEFAULT_SPACE_ID)
    if space is None:
        space = Space(
            id=DEFAULT_SPACE_ID,
            user_id=SYSTEM_USER_ID,
            name=DEFAULT_COURSE_LABEL,
            description="数据结构固定协作课程",
            color="#3B82F6",
            is_collaborative=True,
            review_mode=0,
        )
        db.add(space)
    else:
        space.name = DEFAULT_COURSE_LABEL
        space.is_collaborative = True
    await db.flush()

    owner_member = await db.scalar(
        select(SpaceMember).where(
            SpaceMember.space_id == DEFAULT_SPACE_ID,
            SpaceMember.user_id == SYSTEM_USER_ID,
        )
    )
    if owner_member is None:
        db.add(
            SpaceMember(
                id=uuid5(COURSE_NAMESPACE, "member:system-owner"),
                space_id=DEFAULT_SPACE_ID,
                user_id=SYSTEM_USER_ID,
                role=SpaceMemberRole.OWNER,
                color=get_next_color(0),
                can_edit_graph=True,
            )
        )

    existing_nodes = {
        node.label: node
        for node in (
            await db.execute(select(Node).where(Node.space_id == DEFAULT_SPACE_ID))
        ).scalars()
    }
    for parsed_node in course_graph.nodes:
        if parsed_node.label not in existing_nodes:
            node = Node(
                id=node_id(parsed_node.label),
                space_id=DEFAULT_SPACE_ID,
                label=parsed_node.label,
                mastery=parsed_node.mastery,
            )
            db.add(node)
            existing_nodes[parsed_node.label] = node
    await db.flush()

    existing_edge_ids = set(
        (
            await db.execute(select(Edge.id).where(Edge.space_id == DEFAULT_SPACE_ID))
        ).scalars()
    )
    for parsed_edge in course_graph.edges:
        edge_type = (
            EdgeType.KNOWLEDGE_TREE
            if parsed_edge.edge_type == "knowledge_tree"
            else EdgeType.ADVANCED
        )
        source = parsed_edge.source_label
        target = parsed_edge.target_label
        deterministic_id = edge_id(edge_type, source, target)
        if deterministic_id in existing_edge_ids:
            continue
        db.add(
            Edge(
                id=deterministic_id,
                space_id=DEFAULT_SPACE_ID,
                from_node_id=existing_nodes[source].id,
                to_node_id=existing_nodes[target].id,
                type=edge_type,
                user_id=None,
            )
        )

    user_ids = (
        await db.execute(select(User.id).where(User.id != SYSTEM_USER_ID))
    ).scalars().all()
    for user_id in user_ids:
        await ensure_default_space_membership(db, user_id)

    await db.commit()
