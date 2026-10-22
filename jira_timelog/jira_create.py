"""Create/edit epics and stories in Jira from approved requests. Sub-tasks reuse
runner.run_create. All field values beyond summary/description/parent are applied via
jira_fields.apply_extra_fields — never hardcoded per-field-name logic here."""

from .adf import text_to_adf
from .jira_fields import apply_extra_fields


def epic_fields(cfg, req: dict, account_id: str) -> dict:
    category = (req.get("category") or "").strip()
    title = (req.get("title") or "").strip()
    summary = f"[{category}] {title}" if category else title
    fields = {
        "project": {"key": cfg.project},
        "issuetype": {"id": cfg.epic_type_id},
        "summary": summary,
        "description": text_to_adf(req.get("description") or "-"),
        "assignee": {"id": req.get("assignee_id") or account_id},
        "reporter": {"id": req.get("reporter_id") or account_id},
    }
    apply_extra_fields(cfg, fields, req)
    _apply_dates(cfg, fields, req)
    return fields


def story_fields(cfg, req: dict, account_id: str) -> dict:
    fields = {
        "project": {"key": cfg.project},
        "issuetype": {"id": cfg.story_type_id},
        "parent": {"key": req["epic_key"]},
        "summary": (req.get("title") or "").strip(),
        "description": text_to_adf(req.get("description") or "-"),
        "assignee": {"id": req.get("assignee_id") or account_id},
        "reporter": {"id": req.get("reporter_id") or account_id},
    }
    apply_extra_fields(cfg, fields, req)
    _apply_dates(cfg, fields, req)
    return fields


def _apply_dates(cfg, fields: dict, req: dict) -> None:
    """Epic/story start_date + due_date (same fields the sub-task path already writes) plus
    original_estimate (Jira's native timetracking.originalEstimate, e.g. "3d 4h"). Missing/
    absent silently skipped — never an error if a caller omits any of them."""
    if req.get("start_date"):
        start_field = cfg.field_ids.get("Start Date") or getattr(cfg, "start_date_field", "")
        if start_field:
            fields[start_field] = req["start_date"]
    if req.get("due_date"):
        end_field = getattr(cfg, "end_date_field", "") or "duedate"
        fields[end_field] = req["due_date"]
    if req.get("original_estimate"):
        fields["timetracking"] = {"originalEstimate": req["original_estimate"]}


async def create_epic(client, cfg, req: dict) -> str:
    account_id = (await client.myself())["accountId"]
    return await client.create_issue(epic_fields(cfg, req, account_id))


async def create_story(client, cfg, req: dict) -> str:
    account_id = (await client.myself())["accountId"]
    return await client.create_issue(story_fields(cfg, req, account_id))


async def apply_edit(client, cfg, req: dict) -> str:
    """Apply an approved edit-mode request's diff to its existing Jira ticket. req['diff'] is
    {logical_field_name: {"before":..., "after":...}} — only the 'after' values are written.
    Assignee/reporter are NOT touched on edits (only on create)."""
    after_values = {k: v["after"] for k, v in (req.get("diff") or {}).items()}
    fields = {}
    apply_extra_fields(cfg, fields, after_values)
    if "start_date" in after_values:
        start_field = cfg.field_ids.get("Start Date") or getattr(cfg, "start_date_field", "")
        if start_field:
            fields[start_field] = after_values["start_date"]
    if "due_date" in after_values:
        end_field = getattr(cfg, "end_date_field", "") or "duedate"
        fields[end_field] = after_values["due_date"]
    if "title" in after_values:
        fields["summary"] = after_values["title"]
    if "description" in after_values:
        fields["description"] = text_to_adf(after_values["description"])
    await client.update_issue(req["target_key"], fields)
    return req["target_key"]
