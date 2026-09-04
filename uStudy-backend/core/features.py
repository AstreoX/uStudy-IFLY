"""FastAPI dependencies for runtime feature flags."""

from collections.abc import Callable

from fastapi import HTTPException, status

from config import get_settings


def _feature_dependency(
    setting_name: str,
    feature_name: str,
) -> Callable[[], None]:
    def dependency() -> None:
        if bool(getattr(get_settings(), setting_name, False)):
            return
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "FEATURE_DISABLED",
                "message": f"{feature_name}在实验环境中不可用",
            },
        )

    return dependency


require_public_registration_enabled = _feature_dependency(
    "public_registration_enabled", "邮箱注册与账号恢复功能"
)
require_auth_email_enabled = _feature_dependency(
    "auth_email_enabled", "认证邮件功能"
)
require_apple_login_enabled = _feature_dependency(
    "apple_login_enabled", "Apple 登录功能"
)
require_space_creation_enabled = _feature_dependency(
    "space_creation_enabled", "新建学习空间功能"
)
