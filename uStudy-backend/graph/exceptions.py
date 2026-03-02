"""Knowledge Graph Exceptions"""


class GraphError(Exception):
    """Base exception for graph operations"""

    pass


class NodeNotFoundError(GraphError):
    """Raised when a node is not found"""

    pass


class EdgeNotFoundError(GraphError):
    """Raised when an edge is not found"""

    pass


class DuplicateNodeError(GraphError):
    """Raised when attempting to create a duplicate node"""

    pass


class DuplicateEdgeError(GraphError):
    """Raised when attempting to create a duplicate edge"""

    pass
