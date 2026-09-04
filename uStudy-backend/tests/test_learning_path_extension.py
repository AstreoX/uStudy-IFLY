"""Automatic path extension must only connect existing course nodes."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from chat.tools.graph_tools import GraphToolExecutor


class ExistingNodeGraphService:
    def __init__(self):
        self.space_id = uuid4()
        self.nodes = {
            "B": SimpleNamespace(id=uuid4(), label="B"),
            "C": SimpleNamespace(id=uuid4(), label="C"),
        }
        self.created_node_ids = None

    async def get_node_by_label(self, _space_id, label):
        return self.nodes.get(label)

    async def get_graph(self, _space_id, *, user_id=None, is_collaborative=False):
        self.requested_user_id = user_id
        self.requested_collaborative = is_collaborative
        return {
            "nodes": [
                {"id": str(node.id), "label": node.label}
                for node in self.nodes.values()
            ],
            "edges": [
                {
                    "from_node_id": str(uuid4()),
                    "to_node_id": str(self.nodes["B"].id),
                    "type": "learning_path",
                }
            ],
        }

    async def create_learning_path(self, *, space_id, node_ids, user_id):
        self.created_node_ids = list(node_ids)
        return [SimpleNamespace(id=uuid4())]


@pytest.mark.asyncio
async def test_extend_learning_path_connects_existing_nodes_only():
    service = ExistingNodeGraphService()
    executor = GraphToolExecutor(
        service.space_id,
        user_id=uuid4(),
        is_collaborative=True,
        can_edit_graph=False,
    )

    result = await executor._extend_learning_path(
        {"node_sequence": ["B", "C"]},
        service,
    )

    assert result.success is True
    assert service.created_node_ids == [service.nodes["B"].id, service.nodes["C"].id]
    assert service.requested_user_id == executor.user_id
    assert service.requested_collaborative is True
    assert "已有知识节点" in result.message


@pytest.mark.asyncio
async def test_extend_learning_path_rejects_unknown_node():
    service = ExistingNodeGraphService()
    executor = GraphToolExecutor(service.space_id, user_id=uuid4())

    result = await executor._extend_learning_path(
        {"node_sequence": ["B", "不存在"]},
        service,
    )

    assert result.success is False
    assert "节点不存在" in result.message
    assert service.created_node_ids is None
