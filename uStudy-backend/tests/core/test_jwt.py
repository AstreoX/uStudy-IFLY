"""JWT 工具测试"""

from datetime import timedelta
from uuid import uuid4

import pytest
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    rotate_refresh_token,
)
from db.models import RefreshToken, User


async def create_user(db_session: AsyncSession) -> User:
    user = User(email=f"jwt_{uuid4()}@example.com", nickname="JWT User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestCreateAccessToken:
    """access_token 生成测试"""

    def test_create_access_token_returns_string(self):
        """生成的 token 是字符串"""
        user_id = uuid4()
        token = create_access_token(str(user_id))
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_contains_sub(self):
        """Token payload 包含 sub 字段"""
        user_id = uuid4()
        token = create_access_token(str(user_id))
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)

    def test_create_access_token_contains_exp(self):
        """Token payload 包含 exp 字段"""
        user_id = uuid4()
        token = create_access_token(str(user_id))
        payload = decode_token(token)
        assert "exp" in payload

    def test_create_access_token_contains_type(self):
        """Token payload 包含 type 字段标识 access"""
        user_id = uuid4()
        token = create_access_token(str(user_id))
        payload = decode_token(token)
        assert payload["type"] == "access"


class TestCreateRefreshToken:
    """refresh_token 生成测试"""

    @pytest.mark.asyncio
    async def test_create_refresh_token_returns_string(self, db_session: AsyncSession):
        """生成的 token 是字符串"""
        user = await create_user(db_session)
        token = await create_refresh_token(user.id, db_session)
        assert isinstance(token, str)
        assert len(token) > 0

    @pytest.mark.asyncio
    async def test_create_refresh_token_stored_hash(self, db_session: AsyncSession):
        """refresh token 哈希存储"""
        user = await create_user(db_session)
        token = await create_refresh_token(user.id, db_session)

        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.user_id == user.id)
        )
        stored = result.scalar_one_or_none()
        assert stored is not None
        assert stored.token_hash is not None
        assert stored.token_hash != token

    @pytest.mark.asyncio
    async def test_refresh_token_rotation(self, db_session: AsyncSession):
        """refresh token 轮换"""
        user = await create_user(db_session)
        refresh = await create_refresh_token(user.id, db_session)
        access_new, refresh_new = await rotate_refresh_token(refresh, db_session)

        assert isinstance(access_new, str)
        assert isinstance(refresh_new, str)
        assert refresh_new != refresh


class TestDecodeToken:
    """Token 解码测试"""

    def test_decode_valid_token(self):
        """解码有效 token"""
        user_id = uuid4()
        token = create_access_token(str(user_id))
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)

    def test_decode_invalid_token_raises(self):
        """解码无效 token 抛出异常"""
        with pytest.raises(JWTError):
            decode_token("invalid.token.here")

    def test_decode_expired_token_raises(self):
        """解码过期 token 抛出异常"""
        user_id = uuid4()
        # 使用负数过期时间创建已过期 token
        token = create_access_token(str(user_id), expires_delta=timedelta(seconds=-1))
        with pytest.raises(JWTError):
            decode_token(token)
