"""密码安全模块"""

import bcrypt


def hash_password(password: str) -> str:
    """
    使用 bcrypt 哈希密码

    Args:
        password: 明文密码

    Returns:
        bcrypt 哈希值（自动加盐）
    """
    # 将密码编码为字节
    password_bytes = password.encode("utf-8")
    # 生成盐并哈希
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码

    Args:
        plain_password: 明文密码
        hashed_password: 存储的哈希值

    Returns:
        True 如果密码匹配，否则 False
    """
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)
