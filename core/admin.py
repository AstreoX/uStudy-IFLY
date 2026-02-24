"""Admin access control"""

ADMIN_EMAILS: set[str] = {"tom_cat_gsk@163.com", "1415829227@qq.com"}


def is_admin(email: str) -> bool:
    return email in ADMIN_EMAILS
