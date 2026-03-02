"""Admin-only FastAPI dependencies"""

from fastapi import Depends, HTTPException, status

from auth.dependencies import get_current_user
from core.admin import is_admin
from db.models import User


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency that ensures the caller is an admin user."""
    if not is_admin(current_user.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user
