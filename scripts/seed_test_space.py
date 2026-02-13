"""
种子脚本：创建测试空间和数据结构知识图谱

用法：
    cd uStudy-backend
    python -m scripts.seed_test_space
"""

import asyncio
import random
from uuid import UUID

from sqlalchemy import select

from db.database import AsyncSessionLocal
from db.models import Edge, EdgeType, Node, Space, User

# 数据结构知识树定义
# 格式: (层级, 标签, 预设掌握度)
KNOWLEDGE_TREE = [
    # 根节点（层级 0）
    (0, "数据结构", 80),
    # 一级：数据结构基础
    (1, "数据结构基础", 75),
    (2, "数据结构的定义与分类", 70),
    (3, "逻辑结构与物理结构", 50),
    (3, "抽象数据类型（ADT）", 45),
    (2, "时间复杂度与空间复杂度", 65),
    (3, "大O表示法", 55),
    (3, "最坏情况 / 平均情况 / 最好情况", 40),
    # 一级：线性结构
    (1, "线性结构", 72),
    (2, "数组", 85),
    (3, "顺序存储", 80),
    (3, "动态数组", 60),
    (2, "链表", 80),
    (3, "单链表", 75),
    (3, "双链表", 55),
    (3, "循环链表", 45),
    (2, "栈", 75),
    (3, "顺序栈", 70),
    (3, "链式栈", 50),
    (2, "队列", 70),
    (3, "顺序队列", 65),
    (3, "循环队列", 50),
    (3, "链式队列", 45),
    (3, "双端队列", 35),
    # 一级：非线性结构
    (1, "非线性结构", 55),
    (2, "树结构", 52),
    (3, "树的基本概念", 60),
    (3, "二叉树", 60),
    (4, "满二叉树", 50),
    (4, "完全二叉树", 50),
    (4, "二叉搜索树", 45),
    (3, "平衡二叉树（AVL）", 30),
    (3, "堆", 40),
    (4, "大根堆", 35),
    (4, "小根堆", 35),
    (2, "图结构", 35),
    (3, "图的基本概念", 40),
    (3, "图的存储方式", 30),
    (4, "邻接矩阵", 25),
    (4, "邻接表", 25),
    (3, "图的遍历", 35),
    (4, "深度优先遍历（DFS）", 40),
    (4, "广度优先遍历（BFS）", 35),
    # 一级：查找结构
    (1, "查找结构", 50),
    (2, "顺序查找", 70),
    (2, "二分查找", 60),
    (2, "哈希表", 45),
    (3, "哈希函数", 40),
    (3, "冲突处理", 35),
    (4, "链地址法", 25),
    (4, "开放定址法", 20),
    # 一级：排序算法
    (1, "排序算法", 55),
    (2, "插入排序", 60),
    (3, "直接插入排序", 55),
    (2, "交换排序", 55),
    (3, "冒泡排序", 65),
    (3, "快速排序", 45),
    (2, "选择排序", 50),
    (3, "简单选择排序", 55),
    (3, "堆排序", 30),
    (2, "归并排序", 35),
    # 一级：数据结构应用
    (1, "数据结构应用", 40),
    (2, "表达式求值", 45),
    (2, "内存管理模型", 25),
    (2, "文件系统结构", 20),
]

# 高级连接定义 (跨分支关联)
ADVANCED_CONNECTIONS = [
    ("数组", "顺序存储"),
    ("链表", "动态内存管理"),  # 注意：动态内存管理不在树中，改为内存管理模型
    ("栈", "函数调用栈"),  # 函数调用栈不在树中，跳过
    ("栈", "表达式求值"),
    ("队列", "广度优先遍历（BFS）"),
    ("队列", "二叉树的层序遍历"),  # 不在树中，跳过
    ("数组", "堆"),
    ("堆", "优先队列"),  # 优先队列不在树中，跳过
    ("二叉树", "二叉搜索树"),
    ("二叉搜索树", "二分查找思想"),  # 二分查找思想不在树中，改为二分查找
    ("平衡二叉树（AVL）", "二叉搜索树"),
    ("图结构", "深度优先遍历（DFS）"),
    ("图结构", "广度优先遍历（BFS）"),
    ("哈希表", "快速查找"),  # 快速查找不在树中，跳过
    ("哈希函数", "冲突处理"),
    ("堆", "堆排序"),
    ("分治思想", "快速排序"),  # 分治思想不在树中，跳过
    ("分治思想", "归并排序"),  # 分治思想不在树中，跳过
]

# 实际可用的高级连接（两端节点都在树中）
VALID_ADVANCED_CONNECTIONS = [
    ("数组", "顺序存储"),
    ("栈", "表达式求值"),
    ("队列", "广度优先遍历（BFS）"),
    ("数组", "堆"),
    ("二叉树", "二叉搜索树"),
    ("二叉搜索树", "二分查找"),
    ("平衡二叉树（AVL）", "二叉搜索树"),
    ("图结构", "深度优先遍历（DFS）"),
    ("图结构", "广度优先遍历（BFS）"),
    ("哈希函数", "冲突处理"),
    ("堆", "堆排序"),
]

# 学习路径定义
LEARNING_PATHS = [
    # 一级主题顺序
    ("数据结构基础", "线性结构"),
    ("线性结构", "非线性结构"),
    ("非线性结构", "查找结构"),
    ("查找结构", "排序算法"),
    ("排序算法", "数据结构应用"),
    # 线性结构内部
    ("数组", "链表"),
    ("链表", "栈"),
    ("栈", "队列"),
    # 树相关
    ("树的基本概念", "二叉树"),
    ("二叉树", "二叉搜索树"),
    ("二叉搜索树", "平衡二叉树（AVL）"),
    ("平衡二叉树（AVL）", "堆"),
    # 图相关
    ("图的基本概念", "图的存储方式"),
    ("图的存储方式", "图的遍历"),
    # 查找相关
    ("顺序查找", "二分查找"),
    ("二分查找", "哈希表"),
    # 排序相关
    ("冒泡排序", "快速排序"),
    ("简单选择排序", "堆排序"),
]


async def find_user_by_nickname(db, nickname: str) -> User:
    """根据 nickname 查找用户"""
    result = await db.execute(select(User).where(User.nickname == nickname))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError(f"未找到 nickname='{nickname}' 的用户")
    return user


async def create_space(db, user_id: UUID, name: str, color: str) -> Space:
    """创建学习空间"""
    space = Space(
        user_id=user_id,
        name=name,
        description="数据结构知识图谱测试空间",
        color=color,
    )
    db.add(space)
    await db.flush()
    print(f"✓ 创建空间: {name} (id={space.id})")
    return space


async def create_nodes(db, space_id: UUID, tree: list) -> dict[str, Node]:
    """创建所有知识节点，返回 label -> Node 的映射"""
    node_map = {}
    for level, label, mastery in tree:
        node = Node(
            space_id=space_id,
            label=label,
            mastery=mastery,
        )
        db.add(node)
        node_map[label] = node
    await db.flush()
    print(f"✓ 创建节点: {len(node_map)} 个")
    return node_map


async def create_tree_edges(
    db, space_id: UUID, node_map: dict[str, Node], tree: list
) -> int:
    """创建知识树边（父子层级关系）"""
    edge_count = 0
    parent_stack = []  # (level, label)

    for level, label, _ in tree:
        # 清理栈中层级 >= 当前层级的元素
        while parent_stack and parent_stack[-1][0] >= level:
            parent_stack.pop()

        # 如果有父节点，创建边
        if parent_stack:
            parent_label = parent_stack[-1][1]
            parent_node = node_map[parent_label]
            child_node = node_map[label]

            edge = Edge(
                space_id=space_id,
                from_node_id=parent_node.id,
                to_node_id=child_node.id,
                type=EdgeType.KNOWLEDGE_TREE,
            )
            db.add(edge)
            edge_count += 1

        # 将当前节点压入栈
        parent_stack.append((level, label))

    await db.flush()
    print(f"✓ 创建知识树边: {edge_count} 条")
    return edge_count


async def create_advanced_edges(
    db, space_id: UUID, node_map: dict[str, Node], connections: list
) -> int:
    """创建高级连接边"""
    edge_count = 0
    for from_label, to_label in connections:
        if from_label not in node_map or to_label not in node_map:
            print(f"  ⚠ 跳过: {from_label} -> {to_label} (节点不存在)")
            continue

        from_node = node_map[from_label]
        to_node = node_map[to_label]

        edge = Edge(
            space_id=space_id,
            from_node_id=from_node.id,
            to_node_id=to_node.id,
            type=EdgeType.ADVANCED,
        )
        db.add(edge)
        edge_count += 1

    await db.flush()
    print(f"✓ 创建高级连接边: {edge_count} 条")
    return edge_count


async def create_learning_path_edges(
    db, space_id: UUID, node_map: dict[str, Node], paths: list
) -> int:
    """创建学习路径边"""
    edge_count = 0
    for from_label, to_label in paths:
        if from_label not in node_map or to_label not in node_map:
            print(f"  ⚠ 跳过: {from_label} -> {to_label} (节点不存在)")
            continue

        from_node = node_map[from_label]
        to_node = node_map[to_label]

        edge = Edge(
            space_id=space_id,
            from_node_id=from_node.id,
            to_node_id=to_node.id,
            type=EdgeType.LEARNING_PATH,
        )
        db.add(edge)
        edge_count += 1

    await db.flush()
    print(f"✓ 创建学习路径边: {edge_count} 条")
    return edge_count


async def main():
    """主函数"""
    print("=" * 50)
    print("种子脚本：创建测试空间和数据结构知识图谱")
    print("=" * 50)

    async with AsyncSessionLocal() as db:
        try:
            # 1. 查找用户
            print("\n[1/6] 查找用户 AstreoX...")
            user = await find_user_by_nickname(db, "AstreoX")
            print(f"✓ 找到用户: {user.nickname} (id={user.id})")

            # 2. 创建学习空间
            print("\n[2/6] 创建学习空间...")
            space = await create_space(db, user.id, "测试空间", "#4A90D9")

            # 3. 创建节点
            print("\n[3/6] 创建知识节点...")
            node_map = await create_nodes(db, space.id, KNOWLEDGE_TREE)

            # 4. 创建知识树边
            print("\n[4/6] 创建知识树边...")
            tree_edge_count = await create_tree_edges(
                db, space.id, node_map, KNOWLEDGE_TREE
            )

            # 5. 创建高级连接边
            print("\n[5/6] 创建高级连接边...")
            advanced_edge_count = await create_advanced_edges(
                db, space.id, node_map, VALID_ADVANCED_CONNECTIONS
            )

            # 6. 创建学习路径边
            print("\n[6/6] 创建学习路径边...")
            path_edge_count = await create_learning_path_edges(
                db, space.id, node_map, LEARNING_PATHS
            )

            # 提交事务
            await db.commit()

            # 输出统计
            print("\n" + "=" * 50)
            print("创建完成！统计信息：")
            print(f"  - 节点数量: {len(node_map)}")
            print(f"  - 知识树边: {tree_edge_count}")
            print(f"  - 高级连接边: {advanced_edge_count}")
            print(f"  - 学习路径边: {path_edge_count}")
            print(f"  - 空间 ID: {space.id}")
            print("=" * 50)

        except Exception as e:
            await db.rollback()
            print(f"\n✗ 错误: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(main())
