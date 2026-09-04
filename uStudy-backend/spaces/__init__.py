"""学习空间模块"""

__all__ = ["router"]


def __getattr__(name):
    if name == "router":
        from spaces.router import router

        return router
    raise AttributeError(f"module 'spaces' has no attribute {name!r}")
