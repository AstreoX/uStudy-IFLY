"""配置测试"""

import pytest

from config import Settings


class TestJWTConfig:
    """JWT 配置测试"""

    def test_jwt_secret_key_exists(self):
        """JWT 密钥配置存在"""
        settings = Settings()
        assert hasattr(settings, "jwt_secret_key")
        assert settings.jwt_secret_key is not None

    def test_jwt_algorithm_default(self):
        """JWT 算法默认值"""
        settings = Settings()
        assert settings.jwt_algorithm == "HS256"

    def test_access_token_expire_minutes_default(self):
        """Access Token 过期时间默认 15 分钟"""
        settings = Settings()
        assert settings.access_token_expire_minutes == 15

    def test_refresh_token_expire_days_default(self):
        """Refresh Token 过期时间默认 7 天"""
        settings = Settings()
        assert settings.refresh_token_expire_days == 7
