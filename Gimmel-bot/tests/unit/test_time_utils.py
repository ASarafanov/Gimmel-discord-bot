from datetime import datetime, timezone

from absence_bot.time_utils import calculate_absence_days


def test_same_date_gives_zero_days() -> None:
    last_seen = "2024-01-01T10:00:00+00:00"
    report_at = datetime(2024, 1, 1, 23, 0, tzinfo=timezone.utc)
    assert calculate_absence_days(last_seen, report_at, "UTC") == 0


def test_cross_midnight_gives_one_day() -> None:
    last_seen = "2024-01-01T23:59:00+00:00"
    report_at = datetime(2024, 1, 2, 0, 1, tzinfo=timezone.utc)
    assert calculate_absence_days(last_seen, report_at, "UTC") == 1


def test_dst_boundary_uses_calendar_days() -> None:
    last_seen = "2024-03-30T22:30:00+00:00"
    report_at = datetime(2024, 3, 31, 21, 30, tzinfo=timezone.utc)
    assert calculate_absence_days(last_seen, report_at, "Europe/Helsinki") == 1
