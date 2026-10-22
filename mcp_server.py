#!/usr/bin/env python3
"""MCP server wrapping the Jira Automation FastAPI backend (http://localhost:8000).
Run: python mcp_server.py   — communicates via stdio, FastAPI must be running."""

import os
from datetime import date

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = os.getenv("JIRA_MCP_API_BASE", "http://localhost:8000")
DEFAULT_PROJECT = os.getenv("JIRA_PROJECT", "")

mcp = FastMCP("jira-automation")


async def _get(path: str, **params) -> dict | list:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{API_BASE}{path}", params=params)
        r.raise_for_status()
        return r.json()


async def _post(path: str, body: dict) -> dict | list:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{API_BASE}{path}", json=body)
        r.raise_for_status()
        return r.json()


async def _resolve_story_type_id(project_key: str, type_name: str) -> str:
    """Resolve issue type name (Story/Bug/Task) to Jira type ID."""
    types = await _get("/story-types", project=project_key)
    name_lower = type_name.lower()
    for t in types:
        if t["name"].lower() == name_lower:
            return t["id"]
    return types[0]["id"] if types else ""


async def _resolve_subtask_type_id(project_key: str) -> str:
    types = await _get("/subtask-types", project=project_key)
    return types[0]["id"] if types else ""


# ── tools ────────────────────────────────────────────────────────────────────

@mcp.tool()
async def jira_list_projects() -> str:
    """List all Jira projects the user has access to."""
    data = await _get("/projects")
    return "\n".join(f"{p['key']} — {p['name']}" for p in data)


@mcp.tool()
async def jira_list_epics(project: str = DEFAULT_PROJECT) -> str:
    """List open epics assigned to the current user in a project."""
    data = await _get("/epics", project=project, open_only=True, mine=True)
    if not data:
        return "No open epics found."
    return "\n".join(f"{e['key']} [{e['status']}] — {e['summary']}" for e in data)


@mcp.tool()
async def jira_list_stories(project: str = DEFAULT_PROJECT, epic_key: str = "") -> str:
    """List stories/bugs/tasks in a project or under a specific epic."""
    if epic_key:
        data = await _get(f"/epics/{epic_key}/stories")
    else:
        data = await _get("/stories", project=project)
    if not data:
        return "No stories found."
    return "\n".join(f"{s['key']} [{s['status']}] — {s['summary']}" for s in data)


@mcp.tool()
async def jira_list_bugs(project: str = DEFAULT_PROJECT, epic_key: str = "") -> str:
    """List bugs in a project or under a specific epic."""
    if epic_key:
        data = await _get(f"/epics/{epic_key}/bugs")
    else:
        data = await _get("/bugs", project=project)
    if not data:
        return "No bugs found."
    return "\n".join(f"{s['key']} [{s['status']}] — {s['summary']}" for s in data)


@mcp.tool()
async def jira_list_tasks(project: str = DEFAULT_PROJECT, epic_key: str = "") -> str:
    """List tasks in a project or under a specific epic."""
    if epic_key:
        data = await _get(f"/epics/{epic_key}/tasks")
    else:
        data = await _get("/tasks", project=project)
    if not data:
        return "No tasks found."
    return "\n".join(f"{s['key']} [{s['status']}] — {s['summary']}" for s in data)


@mcp.tool()
async def jira_list_unassigned_epics(project: str = DEFAULT_PROJECT) -> str:
    """List unassigned epics in a project."""
    data = await _get("/unassigned/epics", project=project)
    if not data:
        return "No unassigned epics found."
    return "\n".join(f"{e['key']} [{e['status']}] — {e['summary']}" for e in data)


@mcp.tool()
async def jira_list_unassigned_subtasks(story_key: str = "", project: str = DEFAULT_PROJECT) -> str:
    """List unassigned subtasks under a story (pass story_key) or across a whole project."""
    if story_key:
        data = await _get(f"/stories/{story_key}/unassigned-subtasks")
    else:
        data = await _get("/unassigned/subtasks", project=project)
    if not data:
        return "No unassigned subtasks found."
    return "\n".join(f"{s['key']} [{s['status']}] — {s['summary']}" for s in data)


@mcp.tool()
async def jira_list_unassigned_stories(project: str = DEFAULT_PROJECT, epic_key: str = "") -> str:
    """List unassigned stories in a project or under a specific epic."""
    params = {"project": project}
    if epic_key:
        params["epic_key"] = epic_key
    data = await _get("/unassigned/stories", **params)
    if not data:
        return "No unassigned stories found."
    return "\n".join(f"{s['key']} [{s['status']}] — {s['summary']}" for s in data)


@mcp.tool()
async def jira_list_unassigned_bugs(project: str = DEFAULT_PROJECT, epic_key: str = "") -> str:
    """List unassigned bugs in a project or under a specific epic."""
    params = {"project": project}
    if epic_key:
        params["epic_key"] = epic_key
    data = await _get("/unassigned/bugs", **params)
    if not data:
        return "No unassigned bugs found."
    return "\n".join(f"{s['key']} [{s['status']}] — {s['summary']}" for s in data)


@mcp.tool()
async def jira_list_unassigned_tasks(project: str = DEFAULT_PROJECT, epic_key: str = "") -> str:
    """List unassigned tasks in a project or under a specific epic."""
    params = {"project": project}
    if epic_key:
        params["epic_key"] = epic_key
    data = await _get("/unassigned/tasks", **params)
    if not data:
        return "No unassigned tasks found."
    return "\n".join(f"{s['key']} [{s['status']}] — {s['summary']}" for s in data)


@mcp.tool()
async def jira_list_subtasks(story_key: str) -> str:
    """List subtasks under a story/bug/task."""
    data = await _get(f"/stories/{story_key}/subtasks")
    if not data:
        return f"No subtasks under {story_key}."
    return "\n".join(f"{s['key']} [{s['status']}] — {s['summary']}" for s in data)


@mcp.tool()
async def jira_get_issue_parents(issue_key: str) -> str:
    """Get the story and epic parents of a subtask."""
    data = await _get(f"/issues/{issue_key}/parents")
    parts = []
    if data.get("story_key"):
        parts.append(f"Story: {data['story_key']} — {data.get('story_summary','')}")
    if data.get("epic_key"):
        parts.append(f"Epic: {data['epic_key']} — {data.get('epic_summary','')}")
    return "\n".join(parts) if parts else "No parents found."


@mcp.tool()
async def jira_create_story(
    title: str,
    issue_type: str = "Story",
    project: str = DEFAULT_PROJECT,
    epic_key: str = "",
    description: str = "",
    acceptance: str = "",
    start_date: str = "",
    end_date: str = "",
) -> str:
    """Create a Story, Bug, or Task in Jira.

    Args:
        title: Issue summary/title.
        issue_type: 'Story', 'Bug', or 'Task'.
        project: Jira project key (e.g. WAR).
        epic_key: Parent epic key (optional).
        description: Issue description.
        acceptance: Acceptance criteria (required for Bug type).
        start_date: YYYY-MM-DD (defaults to today).
        end_date: YYYY-MM-DD due date (defaults to today).
    """
    type_id = await _resolve_story_type_id(project, issue_type)
    today = date.today().isoformat()
    data = await _post("/story", {
        "projectKey": project,
        "issueTypeId": type_id,
        "title": title,
        "description": description or "-",
        "acceptance": acceptance or "-",
        "epicKey": epic_key or None,
        "startDate": start_date or today,
        "endDate": end_date or today,
    })
    return f"Created {data['key']}: {title}"


@mcp.tool()
async def jira_create_subtask(
    story_key: str,
    title: str,
    description: str = "",
    acceptance: str = "",
    start_date: str = "",
    end_date: str = "",
    project: str = DEFAULT_PROJECT,
    time_spent: str = "",
    end_time: str = "",
    log_date: str = "",
    close_after: bool = False,
) -> str:
    """Create a subtask under a story.

    Args:
        story_key: Parent story/task key (e.g. WAR-123).
        title: Subtask summary.
        description: What needs to be done.
        acceptance: Acceptance criteria.
        start_date: YYYY-MM-DD.
        end_date: YYYY-MM-DD due date.
        project: Jira project key.
        time_spent: Optional worklog (e.g. '2h 30m').
        end_time: Worklog end time (e.g. '17:00').
        log_date: Worklog date YYYY-MM-DD (defaults to today).
        close_after: Close the subtask after logging time.
    """
    today = date.today().isoformat()
    type_id = await _resolve_subtask_type_id(project)
    worklog = None
    if time_spent and end_time:
        worklog = {
            "date": log_date or today,
            "timeSpent": time_spent,
            "endTime": end_time,
        }
    data = await _post("/subtask", {
        "storyKey": story_key,
        "projectKey": project,
        "issueTypeId": type_id,
        "title": title,
        "description": description or "-",
        "acceptance": acceptance or "-",
        "startDate": start_date or today,
        "endDate": end_date or today,
        "worklogs": [worklog] if worklog else [],
        "closeAfter": close_after,
    })
    key = data.get("subtaskKey", "?")
    msg = f"Created {key}: {title}"
    if worklog:
        msg += f" · logged {time_spent}"
    if close_after:
        msg += " · closed"
    return msg


@mcp.tool()
async def jira_log_time(
    subtask_key: str,
    time_spent: str,
    end_time: str,
    log_date: str = "",
    description: str = "",
    close: bool = False,
) -> str:
    """Log time on an existing subtask.

    Args:
        subtask_key: Jira issue key (e.g. WAR-8770).
        time_spent: Duration string (e.g. '2h 30m', '1h').
        end_time: End time in HH:MM (e.g. '17:00').
        log_date: YYYY-MM-DD (defaults to today).
        description: Work description.
        close: Close the subtask after logging.
    """
    today = date.today().isoformat()
    data = await _post("/timelog", {
        "subtaskKey": subtask_key,
        "date": log_date or today,
        "timeSpent": time_spent,
        "endTime": end_time,
        "description": description,
        "close": close,
    })
    failed = [s for s in data.get("steps", []) if s.get("status") != "ok"]
    if failed:
        return "Failed: " + "; ".join(s.get("msg", "error") for s in failed)
    return f"Logged {time_spent} on {subtask_key}" + (" · closed" if close else "")


@mcp.tool()
async def jira_transition_issue(issue_key: str, status: str) -> str:
    """Change the status of any Jira issue.

    Args:
        issue_key: e.g. WAR-123.
        status: Target status name (e.g. 'In Progress', 'Done', 'In Review').
    """
    data = await _post(f"/issues/{issue_key}/transition", {"status": status})
    return f"{data['key']} → {data['status']}"


@mcp.tool()
async def jira_list_statuses(project: str = DEFAULT_PROJECT, issue_type: str = "story") -> str:
    """List available statuses for an issue type in a project.

    Args:
        project: Jira project key.
        issue_type: 'epic', 'story', 'bug', 'task', or 'subtask'.
    """
    data = await _get("/statuses", project=project, level=issue_type)
    return ", ".join(data) if data else "No statuses found."


@mcp.tool()
async def jira_list_link_types() -> str:
    """List all available link labels to use with jira_link_issues.
    Returns both directions for each type (e.g. 'blocks' and 'is blocked by')."""
    data = await _get("/link-types")
    if not data:
        return "No link types found."
    lines = []
    for t in data:
        lines.append(f"• {t['outward']}  /  {t['inward']}  (type: {t['name']})")
    return "\n".join(lines)


@mcp.tool()
async def jira_link_issues(
    source_key: str,
    target_key: str,
    label: str = "relates to",
) -> str:
    """Link two Jira work items using a directional label exactly as shown in Jira's UI.

    Args:
        source_key: The issue you're linking FROM (e.g. WAR-123).
        target_key: The issue you're linking TO (e.g. WAR-456).
        label: Direction label as it appears in Jira — e.g. 'blocks', 'is blocked by',
               'relates to', 'clones', 'is cloned by', 'duplicates', 'is duplicated by'.
               Use jira_list_link_types to see all available options.
    """
    data = await _post("/issues/link", {
        "sourceKey": source_key,
        "targetKey": target_key,
        "label": label,
    })
    return f"{source_key} {data['label']} {target_key}"


if __name__ == "__main__":
    mcp.run()
