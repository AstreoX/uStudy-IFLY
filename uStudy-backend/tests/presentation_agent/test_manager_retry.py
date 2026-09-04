from presentation_agent.manager import app as manager_app
from presentation_agent.models import RunCreateRequest, RunStatus


def test_manager_retries_failed_container_with_same_run_and_workspace(tmp_path, monkeypatch):
    request = RunCreateRequest(
        run_id="run-retry",
        project_id="project-retry",
        user_id="user-retry",
        space_id="space-retry",
        gateway_url="http://backend:8000/api/internal/presentation-agent/runs/run-retry",
        capability_token="x" * 32,
        instruction="make deck",
        max_attempts=5,
        max_seconds=1800,
    )
    state = {
        "request": request.model_dump(mode="json"),
        "attempt": 1,
        "created_at": 100.0,
        "deadline_at": 1900.0,
        "next_retry_at": None,
    }

    class FakeDocker:
        def __init__(self):
            self.removed = []
            self.created = []

        def inspect_run(self, run_id):
            return RunStatus(
                run_id=run_id,
                project_id="project-retry",
                container_name="container",
                status="failed",
                exit_code=75,
            )

        def remove_run(self, run_id):
            self.removed.append(run_id)

        def create_run(self, retry_request):
            self.created.append(retry_request)

    fake = FakeDocker()
    monkeypatch.setattr(manager_app, "STATE_DIR", tmp_path)
    monkeypatch.setattr(manager_app, "docker", fake)
    manager_app._save_run_state(state)

    manager_app._reconcile_retries(100.0)
    scheduled = manager_app._load_run_state("run-retry")
    assert scheduled["next_retry_at"] == 102.0

    monkeypatch.setattr(manager_app.time, "time", lambda: 103.0)
    manager_app._reconcile_retries(103.0)
    resumed = manager_app._load_run_state("run-retry")
    assert fake.removed == ["run-retry"]
    assert fake.created[0].attempt == 2
    assert resumed["attempt"] == 2
    assert resumed["next_retry_at"] is None
