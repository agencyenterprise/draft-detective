"""Unit tests for the dashboard window and its activity buckets."""

from datetime import UTC, datetime, timedelta

from lib.services.admin_dashboard.models import ActivityGranularity
from lib.services.admin_dashboard.queries import _bucket_starts
from lib.services.admin_dashboard.window import DashboardWindow


def _window(
    days: int, granularity: ActivityGranularity, end: datetime
) -> DashboardWindow:
    span = timedelta(days=days)
    return DashboardWindow(
        days=days,
        start=end - span,
        end=end,
        previous_start=end - 2 * span,
        granularity=granularity,
    )


def test_previous_window_is_adjacent_and_equal_length():
    window = DashboardWindow.for_days(30)

    assert window.end - window.start == timedelta(days=30)
    assert window.start - window.previous_start == timedelta(days=30)


def test_short_windows_bucket_by_day_long_ones_by_week():
    assert DashboardWindow.for_days(7).granularity == ActivityGranularity.DAY
    assert DashboardWindow.for_days(90).granularity == ActivityGranularity.DAY
    assert DashboardWindow.for_days(365).granularity == ActivityGranularity.WEEK


def test_daily_buckets_cover_every_day_in_the_window():
    end = datetime(2026, 3, 10, 14, 30, tzinfo=UTC)
    buckets = _bucket_starts(_window(7, ActivityGranularity.DAY, end))

    assert buckets[0].isoformat() == "2026-03-03"
    assert buckets[-1].isoformat() == "2026-03-10"
    assert len(buckets) == 8  # both partial end days are shown
    assert all(
        (later - earlier) == timedelta(days=1)
        for earlier, later in zip(buckets, buckets[1:])
    )


def test_weekly_buckets_start_on_monday():
    # 2026-03-10 is a Tuesday; the window opens mid-week a year earlier.
    end = datetime(2026, 3, 10, tzinfo=UTC)
    buckets = _bucket_starts(_window(365, ActivityGranularity.WEEK, end))

    assert all(bucket.weekday() == 0 for bucket in buckets)
    assert buckets[0].isoformat() == "2025-03-10"  # the Monday of the opening week
    assert buckets[-1] <= end.date()
    assert len(buckets) == 53
