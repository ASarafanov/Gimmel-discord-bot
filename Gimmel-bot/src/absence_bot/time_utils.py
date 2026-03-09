from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(dt: Optional[datetime] = None) -> str:
    value = dt or now_utc()
    return value.astimezone(timezone.utc).isoformat()


def parse_utc_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_timezone(tz_name: str) -> None:
    ZoneInfo(tz_name)


def validate_daily_time(value: str) -> None:
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError("daily_time must be HH:MM")
    hour = int(parts[0])
    minute = int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("daily_time must be HH:MM")


def calculate_absence_days(last_seen_at_utc: str, report_at_utc: datetime, tz_name: str) -> int:
    tz = ZoneInfo(tz_name)
    last_seen_local = parse_utc_iso(last_seen_at_utc).astimezone(tz).date()
    report_local = report_at_utc.astimezone(tz).date()
    return (report_local - last_seen_local).days


def format_local_date(utc_iso_value: Optional[str], tz_name: str) -> Optional[str]:
    if utc_iso_value is None:
        return None
    tz = ZoneInfo(tz_name)
    return parse_utc_iso(utc_iso_value).astimezone(tz).date().isoformat()
