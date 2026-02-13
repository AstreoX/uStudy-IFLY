"""
清理重复节点脚本

运行前请先备份数据库！

使用方法:
    cd ustudy-backend
    python -m scripts.cleanup_duplicate_nodes           # 预览模式
    python -m scripts.cleanup_duplicate_nodes --execute # 执行清理
    python -m scripts.cleanup_duplicate_nodes --verify  # 验证结果
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Tuple
from uuid import UUID

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import AsyncSessionLocal
from db.models import Node, Edge


async def find_duplicates(session: AsyncSession) -> List[Tuple[UUID, str, int]]:
    """查找所有重复节点组"""
    result = await session.execute(
        select(Node.space_id, Node.label, func.count(Node.id).label("cnt"))
        .group_by(Node.space_id, Node.label)
        .having(func.count(Node.id) > 1)
    )
    return result.all()


async def migrate_edge_safely(
    session: AsyncSession,
    edge: Edge,
    keep_node_id: UUID,
    is_from_edge: bool,
) -> bool:
    """
    安全迁移边，检查是否会创建重复

    Returns:
        True 如果边被迁移，False 如果边被删除（因为会创建重复）
    """
    if is_from_edge:
        new_from = keep_node_id
        new_to = edge.to_node_id
    else:
        new_from = edge.from_node_id
        new_to = keep_node_id

    # 检查是否会创建自循环
    if new_from == new_to:
        await session.delete(edge)
        await session.flush()
        return False

    # 检查是否已存在相同的边
    existing = await session.execute(
        select(Edge).where(
            Edge.space_id == edge.space_id,
            Edge.from_node_id == new_from,
            Edge.to_node_id == new_to,
            Edge.type == edge.type,
        )
    )
    if existing.scalar_one_or_none():
        # 已存在相同边，删除当前边
        await session.delete(edge)
        await session.flush()
        return False

    # 安全迁移
    if is_from_edge:
        edge.from_node_id = keep_node_id
    else:
        edge.to_node_id = keep_node_id

    # 立即刷新以确保后续查询能看到更新
    await session.flush()
    return True


async def cleanup_duplicates(dry_run: bool = True) -> None:
    """
    清理重复节点

    Args:
        dry_run: 如果为 True，只显示将要执行的操作，不实际执行
    """
    async with AsyncSessionLocal() as session:
        try:
            duplicates = await find_duplicates(session)

            if not duplicates:
                print("No duplicate nodes found!")
                return

            print(f"Found {len(duplicates)} duplicate group(s)")
            print("-" * 60)

            total_deleted_nodes = 0
            total_migrated_edges = 0
            total_removed_edges = 0

            for space_id, label, count in duplicates:
                # 截断标签用于显示
                safe_label = label[:50].replace("\n", " ").replace("\r", "")
                print(f"\nSpace: {space_id}")
                print(f"Label: '{safe_label}'")
                print(f"Count: {count}")

                # 获取所有重复节点
                nodes_result = await session.execute(
                    select(Node)
                    .where(Node.space_id == space_id, Node.label == label)
                    .order_by(Node.id)
                )
                nodes = nodes_result.scalars().all()

                keep_node = nodes[0]
                delete_nodes = nodes[1:]

                print(f"  Keep:   {keep_node.id}")
                for dup in delete_nodes:
                    print(f"  Delete: {dup.id}")

                if not dry_run:
                    for dup in delete_nodes:
                        # 获取需要迁移的边（from_node_id = dup.id）
                        from_edges_result = await session.execute(
                            select(Edge).where(Edge.from_node_id == dup.id)
                        )
                        from_edges = from_edges_result.scalars().all()

                        # 获取需要迁移的边（to_node_id = dup.id）
                        to_edges_result = await session.execute(
                            select(Edge).where(Edge.to_node_id == dup.id)
                        )
                        to_edges = to_edges_result.scalars().all()

                        migrated = 0
                        removed = 0

                        # 处理 from_node 边
                        for edge in from_edges:
                            if await migrate_edge_safely(session, edge, keep_node.id, True):
                                migrated += 1
                            else:
                                removed += 1

                        # 处理 to_node 边
                        for edge in to_edges:
                            if await migrate_edge_safely(session, edge, keep_node.id, False):
                                migrated += 1
                            else:
                                removed += 1

                        if migrated > 0 or removed > 0:
                            print(f"    Edges: {migrated} migrated, {removed} removed (duplicates/self-loops)")

                        total_migrated_edges += migrated
                        total_removed_edges += removed

                        # 删除重复节点
                        await session.delete(dup)
                        total_deleted_nodes += 1

            if not dry_run:
                await session.commit()
                print("\n" + "=" * 60)
                print("Cleanup complete!")
                print(f"  Nodes deleted: {total_deleted_nodes}")
                print(f"  Edges migrated: {total_migrated_edges}")
                print(f"  Edges removed: {total_removed_edges}")
            else:
                print("\n" + "=" * 60)
                print("DRY RUN - No changes made. Run with --execute to apply changes.")

        except Exception as e:
            await session.rollback()
            print(f"\nERROR: Cleanup failed - {e}")
            raise


async def verify_cleanup() -> bool:
    """验证清理结果"""
    async with AsyncSessionLocal() as session:
        duplicates = await find_duplicates(session)

        if duplicates:
            print(f"WARNING: {len(duplicates)} duplicate group(s) still exist!")
            for space_id, label, count in duplicates:
                safe_label = label[:50].replace("\n", " ").replace("\r", "")
                print(f"  - '{safe_label}' in space {space_id}: {count} nodes")
            return False
        else:
            print("Verification passed: No duplicate nodes found.")
            return True


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Clean up duplicate nodes in the database"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute the cleanup (default is dry run)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Only verify if duplicates exist",
    )
    args = parser.parse_args()

    if args.verify:
        asyncio.run(verify_cleanup())
    else:
        asyncio.run(cleanup_duplicates(dry_run=not args.execute))


if __name__ == "__main__":
    main()
