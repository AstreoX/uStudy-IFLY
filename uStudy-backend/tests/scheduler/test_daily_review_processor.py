from datetime import date, datetime, timezone

from scheduler.jobs.daily_review_processor import (
    _calculate_days_inactive,
    _get_inactivity_cycle_email_dates,
    _resolve_last_activity_date,
    _should_send_inactivity_care_email,
)


def test_should_not_send_when_user_recently_reused_app():
    today = date(2026, 4, 25)
    last_activity_date = date(2026, 4, 24)

    assert _should_send_inactivity_care_email(
        today=today,
        last_activity_date=last_activity_date,
        sent_at_values=[
            datetime(2026, 4, 22, 8, 0, tzinfo=timezone.utc),
        ],
    ) is False


def test_should_stop_after_three_emails_in_same_inactivity_cycle():
    today = date(2026, 4, 25)

    assert _should_send_inactivity_care_email(
        today=today,
        last_activity_date=date(2026, 4, 20),
        sent_at_values=[
            datetime(2026, 4, 22, 0, 10, tzinfo=timezone.utc),
            datetime(2026, 4, 23, 0, 10, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 0, 10, tzinfo=timezone.utc),
        ],
    ) is False


def test_activity_after_old_emails_starts_new_inactivity_cycle():
    today = date(2026, 4, 25)
    last_activity_date = date(2026, 4, 22)
    sent_dates = _get_inactivity_cycle_email_dates(
        [
            datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 8, 0, tzinfo=timezone.utc),
        ],
        last_activity_date=last_activity_date,
    )

    assert sent_dates == [date(2026, 4, 24)]
    assert _should_send_inactivity_care_email(
        today=today,
        last_activity_date=last_activity_date,
        sent_at_values=[
            datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc),
            datetime(2026, 4, 24, 8, 0, tzinfo=timezone.utc),
        ],
    ) is True


def test_days_inactive_prefers_last_activity_date():
    today = date(2026, 4, 25)

    assert _resolve_last_activity_date(
        date(2026, 4, 22),
        datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc),
    ) == date(2026, 4, 23)
    assert _calculate_days_inactive(
        today=today,
        earliest_due=date(2026, 4, 18),
        last_activity_date=date(2026, 4, 23),
    ) == 2
