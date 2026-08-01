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


class TierDowngradeError(ActivationError):
    """Code tier is lower than user's current tier."""

    def __init__(self, message: str = "您当前的订阅等级高于此激活码，无法降级使用"):
        super().__init__(message, "TIER_DOWNGRADE")
