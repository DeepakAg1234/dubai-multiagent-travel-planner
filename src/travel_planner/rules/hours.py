"""Parse curated opening-hours strings (weekday keys or ``daily``)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, time, timedelta

_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def weekday_key(day: date) -> str:
    return _WEEKDAYS[day.weekday()]


def hours_for(opening_hours: Mapping[str, str] | None, day: date) -> str | None:
    if not opening_hours:
        return None
    if "daily" in opening_hours:
        return opening_hours["daily"]
    return opening_hours.get(weekday_key(day))


def parse_window(raw: str | None) -> tuple[time, time] | None:
    """Return an inclusive start and exclusive-ish end. ``None`` means closed or unknown."""

    if raw is None:
        return None
    text = raw.strip().lower()
    if not text or text in {"closed", "off"}:
        return None
    if text in {"24 hours", "24h", "open 24 hours"}:
        return time(0, 0), time(23, 59)
    if text in {"daylight", "sunrise-sunset"}:
        return time(7, 0), time(18, 0)
    if "-" not in text:
        return None
    start_raw, end_raw = (part.strip() for part in text.split("-", 1))
    start = _parse_clock(start_raw)
    end = _parse_clock(end_raw)
    if start is None or end is None:
        return None
    if end == time(0, 0) and start != time(0, 0):
        end = time(23, 59)
    return start, end


def window_on(opening_hours: Mapping[str, str] | None, day: date) -> tuple[time, time] | None:
    return parse_window(hours_for(opening_hours, day))


def time_in_window(when: time, window: tuple[time, time] | None) -> bool:
    if window is None:
        return True
    start, end = window
    if start <= end:
        return start <= when <= end
    return when >= start or when <= end


def add_minutes(when: time, minutes: int) -> time:
    stamp = timedelta(hours=when.hour, minutes=when.minute) + timedelta(minutes=minutes)
    total = int(stamp.total_seconds() // 60) % (24 * 60)
    return time(total // 60, total % 60)


def minutes_between(start: time, end: time) -> int:
    a = start.hour * 60 + start.minute
    b = end.hour * 60 + end.minute
    if b < a:
        b += 24 * 60
    return b - a


def overlaps(start: time, end: time, window_start: time, window_end: time) -> bool:
    return start < window_end and end > window_start


def _parse_clock(raw: str) -> time | None:
    parts = raw.replace(".", ":").split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return None
    if hour == 24 and minute == 0:
        return time(23, 59)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return time(hour, minute)
