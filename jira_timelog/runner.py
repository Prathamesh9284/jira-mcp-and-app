"""Orchestrates a job's steps against JiraClient, collecting per-step progress.

Critical steps (create, worklog) halt the sequence on failure — no silent
half-done state. Status transitions are SOFT: if a workflow doesn't offer the
named transition (already in that status, different workflow), it's reported as
a note and does NOT block the worklog.
"""

from .client import JiraError

WIP = "Work in Progress"
CLOSED = "Closed"
STORY_STATUS = "Development in progress"


async def _run_steps(steps: list[tuple[str, callable]]) -> dict:
    """Run (label, async fn) steps in order. Stop at first error. Return {status, steps, ...}."""
    log = []
    extra = {}
    for label, fn in steps:
        try:
            out = await fn()
            if isinstance(out, dict):
                note = out.pop("note", None)
                if note:
                    extra.setdefault("notes", []).append(note)
                extra.update(out)
            log.append({"label": label, "status": "ok", "msg": ""})
        except JiraError as e:
            log.append({"label": label, "status": "error", "msg": e.message})
            return {"status": "error", "steps": log, **extra}
        except Exception as e:  # noqa: BLE001 - surface anything as a failed step
            log.append({"label": label, "status": "error", "msg": str(e)})
            return {"status": "error", "steps": log, **extra}
    return {"status": "done", "steps": log, **extra}


def _soft_transition(client, key: str, name: str):
    """Returns an async zero-arg callable that transitions without halting the sequence."""
    async def step():
        try:
            await client.transition_to(key, name)
            return None
        except JiraError as e:
            return {"note": f'{key}: could not set "{name}" — {e.message[:120]}'}
    return step


async def run_create(client, job: dict, tz_offset: str = "+0000") -> dict:
    state = {}

    async def create():
        account = (await client.myself())["accountId"]
        state["key"] = await client.create_subtask(job, account)
        return {"subtaskKey": state["key"]}

    async def wip_transition():
        return await _soft_transition(client, state["key"], WIP)()

    async def story_transition():
        return await _soft_transition(client, job["storyKey"], STORY_STATUS)()

    steps = [
        ("Create subtask", create),
        ("Set subtask Work in Progress", wip_transition),
        ("Set story Development in progress", story_transition),
    ]

    all_worklogs = job.get("worklogs") or ([job["worklog"]] if job.get("worklog") else [])
    for i, wl in enumerate(all_worklogs):
        label = "Log work" if len(all_worklogs) == 1 else f"Log work {i + 1}"
        async def log_work(wl=wl, label=label):
            return await client.add_worklog(state["key"], wl, tz_offset)
        steps.append((label, log_work))

    will_close = bool((all_worklogs and all_worklogs[-1].get("close")) or job.get("closeAfter"))
    if will_close:
        steps.append(("Close subtask", lambda: _soft_transition(client, state["key"], CLOSED)()))

    result = await _run_steps(steps)
    result["finalStatus"] = CLOSED if will_close else WIP
    return result


async def run_log(client, job: dict, tz_offset: str = "+0000") -> dict:
    key = job["subtaskKey"]
    worklog = job["worklog"]

    async def log_work():
        return await client.add_worklog(key, worklog, tz_offset)

    steps = [("Log work", log_work)]
    if worklog.get("close"):
        async def close_step():
            return await _soft_transition(client, key, CLOSED)()
        steps.append(("Close subtask", close_step))
    result = await _run_steps(steps)
    result["subtaskKey"] = key
    result["finalStatus"] = CLOSED if worklog.get("close") else None
    return result
