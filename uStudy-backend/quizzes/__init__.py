"""测试模块"""

__all__ = ["router"]


def __getattr__(name):
    if name == "router":
        from quizzes.router import router

        return router
    raise AttributeError(f"module 'quizzes' has no attribute {name!r}")
