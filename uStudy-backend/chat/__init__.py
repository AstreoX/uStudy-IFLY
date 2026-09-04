"""Chat package.

Keep package initialization lightweight so config-only imports do not pull in
optional runtime dependencies such as Redis-backed tool executors.
"""

__all__: list[str] = []
