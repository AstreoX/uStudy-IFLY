"""笔记模块异常类"""


class NoteError(Exception):
    """笔记通用错误"""

    pass


class NoteNotFoundError(NoteError):
    """笔记不存在"""

    pass


class NoteAccessDeniedError(NoteError):
    """无权访问笔记"""

    pass
