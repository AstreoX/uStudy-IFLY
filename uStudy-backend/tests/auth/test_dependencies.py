"""Auth Dependencies 测试"""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from auth.schemas import RegisterRequest
from auth.service import register
from core.jwt import create_access_token, create_refresh_token


class TestGetCurrentUser:
    """get_current_user 依赖测试"""

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self, db_session: AsyncSession):
        """有效 token 返回用户"""
        # 创建用户
        request = RegisterRequest(
            email="current@example.com",
            password="Password123",
            nickname="Current User",
        )
        created_user = await register(db_session, request)

        # 创建 token
        token = create_access_token(str(created_user.id))

        # 获取当前用户
        user = await get_current_user(token=token, db=db_session)
        assert user.id == created_user.id
        assert user.email == "current@example.com"

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self, db_session: AsyncSession):
        """无效 token 抛出 401"""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="invalid.token", db=db_session)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_raises_401(self, db_session: AsyncSession):
        """使用 refresh token 抛出 401"""
        request = RegisterRequest(
            email="refreshtest@example.com",
            password="Password123",
            nickname="Refresh User",
        )
        user = await register(db_session, request)

        # 使用 refresh token
        refresh = await create_refresh_token(user.id, db_session)
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=refresh, db=db_session)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_nonexistent_user_raises_401(self, db_session: AsyncSession):
        """用户不存在抛出 401"""
        fake_id = uuid4()
        token = create_access_token(str(fake_id))

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, db=db_session)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_missing_token_raises_401(self, db_session: AsyncSession):
        """缺少 token 抛出 401"""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=None, db=db_session)
        assert exc_info.value.status_code == 401
