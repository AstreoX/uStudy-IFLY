"""密码安全模块测试"""

import pytest

from core.security import hash_password, verify_password


class TestHashPassword:
    """hash_password 函数测试"""

    def test_hash_password_returns_bcrypt(self):
        """哈希格式以 $2b$ 开头（bcrypt 格式）"""
        password = "test_password_123"
        hashed = hash_password(password)

        assert hashed.startswith("$2b$")
        assert len(hashed) == 60  # bcrypt 哈希长度

    def test_hash_password_unique_per_call(self):
        """同一密码每次哈希结果不同（盐不同）"""
        password = "same_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2

    def test_hash_password_with_special_chars(self):
        """特殊字符密码哈希正常"""
        password = "P@ssw0rd!#$%^&*()"
        hashed = hash_password(password)

        assert hashed.startswith("$2b$")

    def test_hash_password_with_unicode(self):
        """Unicode 密码哈希正常"""
        password = "密码测试123"
        hashed = hash_password(password)

        assert hashed.startswith("$2b$")


class TestVerifyPassword:
    """verify_password 函数测试"""

    def test_verify_password_correct(self):
        """正确密码验证通过"""
        password = "correct_password"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """错误密码验证失败"""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_case_sensitive(self):
        """密码大小写敏感"""
        password = "CaseSensitive"
        hashed = hash_password(password)

        assert verify_password("casesensitive", hashed) is False
        assert verify_password("CASESENSITIVE", hashed) is False

    def test_verify_password_empty_string(self):
        """空字符串密码验证"""
        password = ""
        hashed = hash_password(password)

        assert verify_password("", hashed) is True
        assert verify_password("not_empty", hashed) is False
