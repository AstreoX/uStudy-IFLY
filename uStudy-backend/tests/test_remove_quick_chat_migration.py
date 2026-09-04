"""Static operation contract for the irreversible Quick Chat cleanup migration."""

import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "remove_quick_chat_v1.py"
)
SPEC = importlib.util.spec_from_file_location("remove_quick_chat_v1", MIGRATION_PATH)
migration = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(migration)


def test_upgrade_removes_quick_chat_data_and_requires_space(monkeypatch):
    statements: list[str] = []
    alterations: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)
    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda *args, **kwargs: alterations.append((args, kwargs)),
    )

    migration.upgrade()

    combined = "\n".join(statements)
    assert "DELETE FROM conversations WHERE space_id IS NULL" in combined
    assert "DELETE FROM feedbacks" in combined
    assert "DELETE FROM api_usage_logs" in combined
    assert "DROP TABLE IF EXISTS quick_chat_tool_tasks" in combined
    assert "DROP TYPE IF EXISTS quickchattooltaskstage" in combined
    assert "DROP TYPE IF EXISTS quickchattooltaskstatus" in combined
    assert len(alterations) == 1
    args, kwargs = alterations[0]
    assert args == ("conversations", "space_id")
    assert kwargs["nullable"] is False
