"""E2E 测试 fixtures

从 graph 测试模块导入共享的 fixtures
"""

# 导入 graph 测试的共享 fixtures
from tests.graph.conftest import (
    graph_test_user,
    graph_test_space,
    sample_graph,
    empty_graph_space,
    circular_graph,
)

# 重新导出以便 pytest 发现
__all__ = [
    "graph_test_user",
    "graph_test_space",
    "sample_graph",
    "empty_graph_space",
    "circular_graph",
]
