"""Pure input validation and job building. No I/O, no network — fully unit-testable."""

import re

ISSUE_KEY = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")
TIME_SPENT = re.compile(r"^(\d+[wdhm])(\s+\d+[wdhm])*$")   # "2h", "2h 30m", "1d 4h"
CLOCK = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_valid_issue_key(s) -> bool:
    return isinstance(s, str) and bool(ISSUE_KEY.match(s))


def is_valid_date(s) -> bool:
    if not isinstance(s, str) or not DATE.match(s):
        return False
    y, m, d = (int(x) for x in s.split("-"))
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return False
    days = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return d <= days[m - 1]


def is_valid_time_spent(s) -> bool:
    return isinstance(s, str) and bool(TIME_SPENT.match(s.strip()))


def is_valid_clock(s) -> bool:
    return isinstance(s, str) and bool(CLOCK.match(s))


def _worklog_errors(inp: dict) -> list[str]:
    e = []
    if not is_valid_date(inp.get("date")):
        e.append("Worklog date must be YYYY-MM-DD.")
    if not is_valid_time_spent(inp.get("timeSpent")):
        e.append('Time spent must look like "2h 30m".')
    if not is_valid_clock(inp.get("endTime")):
        e.append("End time must be HH:MM (24h).")
    return e


def validate_create(inp: dict) -> dict:
    errors = []
    if not is_valid_issue_key(inp.get("storyKey")):
        errors.append("Story key must look like PTA-6049.")
    if not str(inp.get("title") or "").strip():
        errors.append("Title is required.")
    if not is_valid_date(inp.get("startDate")):
        errors.append("Start date must be YYYY-MM-DD.")
    if not is_valid_date(inp.get("endDate")):
        errors.append("End date must be YYYY-MM-DD.")
    if inp.get("logTime"):
        errors.extend(_worklog_errors(inp))
    for i, wl in enumerate(inp.get("worklogs") or []):
        for err in _worklog_errors(wl):
            errors.append(f"Time log {i + 1}: {err}")
    return {"ok": not errors, "errors": errors}


def validate_timelog(inp: dict) -> dict:
    errors = []
    if not is_valid_issue_key(inp.get("subtaskKey")):
        errors.append("Subtask key must look like PTA-6050.")
    errors.extend(_worklog_errors(inp))
    return {"ok": not errors, "errors": errors}


def _worklog_from(inp: dict) -> dict:
    wl = {
        "date": inp.get("date"),
        "timeSpent": str(inp.get("timeSpent", "")).strip(),
        "endTime": inp.get("endTime"),
        "close": bool(inp.get("close")),
    }
    if inp.get("description"):
        wl["description"] = inp["description"]
    return wl


def build_create_job(inp: dict) -> dict:
    worklogs = [_worklog_from(wl) for wl in (inp.get("worklogs") or [])]
    if worklogs and inp.get("closeAfter"):
        worklogs[-1]["close"] = True
    return {
        "type": "CREATE_SUBTASK",
        "storyKey": inp.get("storyKey"),
        "projectKey": inp.get("projectKey"),
        "issueTypeId": inp.get("issueTypeId"),
        "title": str(inp.get("title", "")).strip(),
        "description": inp["description"] if inp.get("description") else "-",
        "acceptance": inp["acceptance"] if inp.get("acceptance") else "-",
        "startDate": inp.get("startDate"),
        "endDate": inp.get("endDate"),
        "worklog": _worklog_from(inp) if inp.get("logTime") else None,
        "worklogs": worklogs,
        "closeAfter": bool(inp.get("closeAfter")),
    }


def build_log_job(inp: dict) -> dict:
    return {"type": "LOG_TIME", "subtaskKey": inp.get("subtaskKey"), "worklog": _worklog_from(inp)}
