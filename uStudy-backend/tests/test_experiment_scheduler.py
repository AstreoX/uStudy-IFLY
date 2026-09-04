"""Scheduler registration tests for the experiment feature flags."""

from types import SimpleNamespace

from scheduler import core as scheduler_core


class RecordingScheduler:
    def __init__(self):
        self.job_ids: list[str] = []

    def add_job(self, _func, **kwargs):
        self.job_ids.append(kwargs["id"])


def test_experiment_scheduler_skips_payment_and_email_jobs(monkeypatch):
    monkeypatch.setattr(
        scheduler_core,
        "get_settings",
        lambda: SimpleNamespace(
            app_env="experiment",
        ),
    )
    scheduler = RecordingScheduler()

    scheduler_core._register_jobs(scheduler)

    assert "cleanup_expired_tool_requests" in scheduler.job_ids
    assert "daily_review_processor" in scheduler.job_ids
    assert "daily_usage_report" not in scheduler.job_ids
    assert "expire_stale_payment_orders" not in scheduler.job_ids
