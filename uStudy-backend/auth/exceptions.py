"""Auth 异常定义"""


class AuthError(Exception):
    """认证基础异常"""

    pass


class EmailAlreadyExistsError(AuthError):
    """邮箱已存在"""

    def __init__(self, email: str):
        self.email = email
        super().__init__(f"Email already exists: {email}")


class InvalidCredentialsError(AuthError):
    """凭证无效（邮箱或密码错误）"""

    def __init__(self, message: str = "Invalid email or password"):
        super().__init__(message)


class InvalidTokenError(AuthError):
    """Token 无效"""

    def __init__(self, message: str = "Invalid token"):
        super().__init__(message)


class AppleAuthError(AuthError):
    """Apple 认证错误"""

    def __init__(self, message: str = "Apple authentication failed"):
        super().__init__(message)


class RateLimitError(AuthError):
    """发送验证码频率限制"""

    def __init__(self, message: str = "Rate limited"):
        super().__init__(message)


class InvalidCodeError(AuthError):
    """验证码错误"""

    def __init__(self, message: str = "Invalid code"):
        super().__init__(message)


class CodeExpiredError(AuthError):
    """验证码过期"""

    def __init__(self, message: str = "Code expired"):
        super().__init__(message)


class TooManyAttemptsError(AuthError):
    """验证码尝试次数过多"""

    def __init__(self, message: str = "Too many attempts"):
        super().__init__(message)


class TokenExpiredError(AuthError):
    """Token 过期"""

    def __init__(self, message: str = "Token expired"):
        super().__init__(message)


class TokenInvalidError(AuthError):
    """Token 无效"""

    def __init__(self, message: str = "Invalid token"):
        super().__init__(message)


class AccountLockedError(AuthError):
    """账户锁定"""

    def __init__(self, message: str = "Account locked"):
        super().__init__(message)


class TokenReuseError(AuthError):
    """Refresh token 被重复使用"""

    def __init__(self, message: str = "Token reuse detected"):
        super().__init__(message)


class SecurityError(AuthError):
    """安全异常"""

    def __init__(self, message: str = "Security error"):
        super().__init__(message)
