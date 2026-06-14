"""pytest 配置和 fixtures"""

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 加载 .env 文件中的环境变量（用于 E2E 测试）
load_dotenv()

# 让单元测试与本地 .env 隔离，避免数据库和布尔配置污染导入阶段。
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from db.database import Base


# 测试数据库 URL（使用内存 SQLite 或测试容器）
# 生产环境应使用 testcontainers-python
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """创建测试用异步引擎"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    # 启用 SQLite 外键约束
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """创建测试用数据库 session"""
    async_session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session_factory() as session:
        yield session
        await session.rollback()
