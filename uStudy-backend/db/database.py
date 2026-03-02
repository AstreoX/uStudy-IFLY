"""数据库连接管理"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

settings = get_settings()

# 创建异步引擎
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout_seconds,
    pool_recycle=settings.db_pool_recycle_seconds,
    pool_pre_ping=True,
)

# 创建异步 session 工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """所有模型的基类"""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入：获取数据库 session

    Usage:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_scoped_session() -> AsyncGenerator[AsyncSession, None]:
    """
    短生命周期 session，用于 SSE 流中按需获取数据库连接。

    与 get_db() 不同，此函数不依赖 FastAPI 的 Depends 机制，
    可在任意异步上下文中使用。session 在 with 块结束时立即释放回连接池。

    注意：此函数不自动提交。调用方需要在适当的地方显式调用 session.commit()。
    如果发生异常，session 会自动回滚。

    Usage:
        async with get_scoped_session() as session:
            result = await session.execute(query)
            await session.commit()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """
    开发阶段：根据模型自动建表

    注意：生产环境应使用 Alembic 迁移
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
