"""Dashboard aggregation: turn per-day logged seconds into KPIs + a weekday grid.

Weekends (Sat/Sun) are excluded entirely — not counted, not shown.
"""

from datetime import date, timedelta

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def compute(totals: dict, weeks: int, today: date) -> dict:
    """totals: {YYYY-MM-DD: seconds}. Returns {days, kpis, start}."""
    start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))  # Monday, `weeks` back
    days = []
    d = start
    while d <= today:
        if d.weekday() < 5:  # Mon–Fri only
            secs = totals.get(d.isoformat(), 0)
            days.append({
                "date": d.isoformat(),
                "week_start": (d - timedelta(days=d.weekday())).isoformat(),
                "weekday_name": WEEKDAY_NAMES[d.weekday()],
                "hours": round(secs / 3600, 2),
                "logged": secs > 0,
            })
        d += timedelta(days=1)

    logged = [x for x in days if x["logged"]]
    total_hours = round(sum(x["hours"] for x in days), 2)
    rate = round(100 * len(logged) / len(days)) if days else 0
    avg = round(total_hours / len(logged), 2) if logged else 0

    # current streak: consecutive weekdays (ending today) with logged time
    streak = 0
    dd = today
    while dd >= start:
        if dd.weekday() < 5:
            if totals.get(dd.isoformat(), 0) > 0:
                streak += 1
            else:
                break
        dd -= timedelta(days=1)

    kpis = {"total_hours": total_hours, "logged_days": len(logged),
            "weekdays": len(days), "rate": rate, "avg": avg, "streak": streak}
    return {"days": days, "kpis": kpis, "start": start.isoformat()}
