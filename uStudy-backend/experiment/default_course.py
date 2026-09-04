"""Idempotent initialization for the fixed Data Structures collaborative course."""

from __future__ import annotations

from uuid import UUID, uuid5

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
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
from experiment.course_catalog import (
    DATA_STRUCTURES_SPACE_ID,
    MANAGED_COURSE_IDS,
)


COURSE_NAMESPACE = UUID("6c56bf7a-7b73-4eb1-9ab2-c741f55d8f9e")
SYSTEM_USER_ID = uuid5(COURSE_NAMESPACE, "system-user")
DEFAULT_SPACE_ID = DATA_STRUCTURES_SPACE_ID
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


def managed_course_membership_id(space_id: UUID, user_id: UUID) -> UUID:
    """Build the stable identity used by automatic managed-course membership."""

    return uuid5(COURSE_NAMESPACE, f"member:{space_id}:{user_id}")


def _membership_insert(db: AsyncSession):
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        return postgresql_insert(SpaceMember)
    if dialect == "sqlite":
        return sqlite_insert(SpaceMember)
    return None


async def ensure_managed_course_memberships(
    db: AsyncSession, user_id: UUID
) -> set[UUID]:
    """Join a real user to every managed course that currently exists.

    Inserts are conflict-safe so concurrent logins cannot create duplicate rows.
    Existing rows are intentionally untouched, which preserves OWNER/TEACHER roles.
    """

    if user_id == SYSTEM_USER_ID:
        return set()

    spaces = list(
        (
            await db.execute(
                select(Space)
                .where(Space.id.in_(MANAGED_COURSE_IDS))
                .order_by(Space.id)
            )
        ).scalars()
    )
    joined_space_ids: set[UUID] = set()
    insert_factory = _membership_insert(db)
    for space in spaces:
        role = (
            SpaceMemberRole.OWNER
            if space.user_id == user_id
            else SpaceMemberRole.MEMBER
        )
        values = {
            "id": managed_course_membership_id(space.id, user_id),
            "space_id": space.id,
            "user_id": user_id,
            "role": role,
            "color": get_next_color(space.id.int ^ user_id.int),
            "can_edit_graph": role == SpaceMemberRole.OWNER,
        }
        if insert_factory is not None:
            statement = insert_factory.values(**values).on_conflict_do_nothing(
                index_elements=["space_id", "user_id"]
            )
            await db.execute(statement)
        else:
            existing = await db.scalar(
                select(SpaceMember.id).where(
                    SpaceMember.space_id == space.id,
                    SpaceMember.user_id == user_id,
                )
            )
            if existing is None:
                db.add(SpaceMember(**values))
        joined_space_ids.add(space.id)
    await db.flush()
    return joined_space_ids


async def ensure_default_space_membership(db: AsyncSession, user_id: UUID) -> bool:
    """Compatibility wrapper that now joins every available managed course."""

    if user_id == SYSTEM_USER_ID:
        return True
    joined_space_ids = await ensure_managed_course_memberships(db, user_id)
    return DEFAULT_SPACE_ID in joined_space_ids


async def _repair_owner_membership(db: AsyncSession, space: Space) -> None:
    """Make ``Space.user_id`` the single owner membership for the default course."""

    owner_member = await db.scalar(
        select(SpaceMember).where(
            SpaceMember.space_id == space.id,
            SpaceMember.user_id == space.user_id,
        )
    )
    if owner_member is None:
        db.add(
            SpaceMember(
                id=managed_course_membership_id(space.id, space.user_id),
                space_id=space.id,
                user_id=space.user_id,
                role=SpaceMemberRole.OWNER,
                color=get_next_color(0),
                can_edit_graph=True,
            )
        )
    else:
        owner_member.role = SpaceMemberRole.OWNER
        owner_member.can_edit_graph = True

    if space.user_id != SYSTEM_USER_ID:
        await db.execute(
            delete(SpaceMember).where(
                SpaceMember.space_id == space.id,
                SpaceMember.user_id == SYSTEM_USER_ID,
            )
        )
    await db.execute(
        SpaceMember.__table__.update()
        .where(
            SpaceMember.space_id == space.id,
            SpaceMember.user_id != space.user_id,
            SpaceMember.role == SpaceMemberRole.OWNER,
        )
        .values(role=SpaceMemberRole.MEMBER, can_edit_graph=False)
    )
    await db.flush()


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

    await _repair_owner_membership(db, space)

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
