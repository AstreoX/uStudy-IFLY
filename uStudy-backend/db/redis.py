"""Redis 连接管理"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import redis.asyncio as redis

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# 全局 Redis 连接池
_redis_pool: Optional[redis.ConnectionPool] = None


def _get_redis_pool() -> redis.ConnectionPool:
    """获取或创建 Redis 连接池（懒加载）"""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,  # 自动解码为字符串
            max_connections=20,
        )
    return _redis_pool


async def get_redis() -> redis.Redis:
    """
    获取 Redis 客户端

    Usage:
        r = await get_redis()
        await r.set("key", "value")
        value = await r.get("key")
    """
    pool = _get_redis_pool()
    return redis.Redis(connection_pool=pool)


@asynccontextmanager
async def get_redis_connection() -> AsyncGenerator[redis.Redis, None]:
    """
    Redis 连接上下文管理器

    Usage:
        async with get_redis_connection() as r:
            await r.set("key", "value")
    """
    r = await get_redis()
    try:
        yield r
    finally:
        await r.aclose()


async def close_redis() -> None:
    """关闭 Redis 连接池（应用退出时调用）"""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None
        logger.info("Redis connection pool closed")


async def check_redis_health() -> bool:
    """检查 Redis 连接健康状态"""
    try:
        r = await get_redis()
        await r.ping()
        return True
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return False
