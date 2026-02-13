"""Activation code exceptions."""


class ActivationError(Exception):
    """Base activation error."""

    def __init__(self, message: str, code: str = "ACTIVATION_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class InvalidCodeError(ActivationError):
    """Invalid activation code."""

    def __init__(self, message: str = "激活码无效"):
        super().__init__(message, "INVALID_CODE")


class CodeAlreadyUsedError(ActivationError):
    """Activation code already used."""

    def __init__(self, message: str = "激活码已被使用"):
        super().__init__(message, "CODE_ALREADY_USED")


class UserAlreadyActivatedError(ActivationError):
    """User already has Alpha status."""

    def __init__(self, message: str = "您已经是 Alpha 用户"):
        super().__init__(message, "ALREADY_ACTIVATED")
