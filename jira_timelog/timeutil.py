"""Pure time math for worklogs. No I/O — unit-testable.

The user supplies date + time-spent + end-time. Native Jira worklog stores a
`started` timestamp plus a duration, so we derive the start clock as
end-time minus duration (which may roll back across midnight).
"""

UNIT_SECONDS = {"w": 5 * 24 * 3600, "d": 24 * 3600, "h": 3600, "m": 60}


def duration_to_seconds(time_spent: str) -> int:
    """'2h 30m' -> 9000. Assumes already-validated format."""
    total = 0
    for token in time_spent.strip().split():
        total += int(token[:-1]) * UNIT_SECONDS[token[-1]]
    return total


def subtract_duration(date: str, end_clock: str, time_spent: str) -> tuple[str, str]:
    """Return (start_date, start_clock 'HH:MM') = (date @ end_clock) - duration.

    Rolls the date back if the subtraction crosses midnight.
    """
    y, mo, d = (int(x) for x in date.split("-"))
    hh, mm = (int(x) for x in end_clock.split(":"))
    end_min = hh * 60 + mm
    start_total = end_min - duration_to_seconds(time_spent) // 60

    day_offset = 0
    while start_total < 0:
        start_total += 24 * 60
        day_offset += 1

    start_hh, start_mm = divmod(start_total, 60)
    from datetime import date as _date, timedelta
    start_day = _date(y, mo, d) - timedelta(days=day_offset)
    return start_day.isoformat(), f"{start_hh:02d}:{start_mm:02d}"


def started_iso(date: str, end_clock: str, time_spent: str, tz_offset: str = "+0000") -> str:
    """Build the Jira `started` timestamp (start = end - duration).

    Format: 2026-07-09T14:30:00.000+0000 (Jira requires milliseconds + offset).
    """
    start_date, start_clock = subtract_duration(date, end_clock, time_spent)
    return f"{start_date}T{start_clock}:00.000{tz_offset}"
