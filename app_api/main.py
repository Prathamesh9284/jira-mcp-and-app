import time
from contextlib import asynccontextmanager
from datetime import date, timedelta

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from jira_timelog import dashboard, validate, runner
from jira_timelog import jira_create as jc
from jira_timelog.client import JiraClient, JiraError
from jira_timelog.config import Config

from .schemas import SubtaskCreate, StoryCreate, TimelogCreate
from jira_timelog.adf import text_to_adf
from jira_timelog.jira_fields import apply_extra_fields

cfg = Config.from_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.jira = JiraClient(cfg)
    cfg.field_ids = await app.state.jira.resolve_fields()
    yield
    await app.state.jira.aclose()


app = FastAPI(title="Jira Automation API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _jira(request: Request) -> JiraClient:
    return request.app.state.jira


@app.get("/health")
async def health():
    missing = cfg.missing()
    return {"jira": not missing, "llm": cfg.llm_ready, "missing": missing}


@app.get("/config")
async def get_config():
    return {"default_project": cfg.project}


@app.get("/projects")
async def list_projects_(request: Request):
    try:
        return await _jira(request).list_projects()
    except JiraError:
        return []


@app.get("/epics")
async def list_epics_(request: Request, project: str = cfg.project, open_only: bool = False,
                      mine: bool = False):
    try:
        return await _jira(request).list_epics(project, open_only, mine)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/epics/{epic_key}/stories")
async def list_stories_(epic_key: str, request: Request):
    try:
        return await _jira(request).list_stories(epic_key)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/epics/{epic_key}/bugs")
async def list_bugs_(epic_key: str, request: Request):
    try:
        return await _jira(request).list_bugs(epic_key)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/epics/{epic_key}/tasks")
async def list_tasks_(epic_key: str, request: Request):
    try:
        return await _jira(request).list_tasks(epic_key)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/stories")
async def list_project_stories_(request: Request, project: str = cfg.project):
    try:
        return await _jira(request).list_project_stories(project)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/bugs")
async def list_project_bugs_(request: Request, project: str = cfg.project):
    try:
        return await _jira(request).list_project_bugs(project)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/tasks")
async def list_project_tasks_(request: Request, project: str = cfg.project):
    try:
        return await _jira(request).list_project_tasks(project)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/unassigned/epics")
async def list_unassigned_epics_(request: Request, project: str = cfg.project):
    try:
        return await _jira(request).list_unassigned_epics(project)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/unassigned/stories")
async def list_unassigned_stories_(request: Request, project: str = cfg.project, epic_key: str = ""):
    try:
        return await _jira(request).list_unassigned_stories(project, epic_key)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/unassigned/bugs")
async def list_unassigned_bugs_(request: Request, project: str = cfg.project, epic_key: str = ""):
    try:
        return await _jira(request).list_unassigned_bugs(project, epic_key)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/unassigned/tasks")
async def list_unassigned_tasks_(request: Request, project: str = cfg.project, epic_key: str = ""):
    try:
        return await _jira(request).list_unassigned_tasks(project, epic_key)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/unassigned/subtasks")
async def list_project_unassigned_subtasks_(request: Request, project: str = cfg.project):
    try:
        return await _jira(request).list_project_unassigned_subtasks(project)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/stories/{story_key}/unassigned-subtasks")
async def list_unassigned_subtasks_(story_key: str, request: Request):
    try:
        return await _jira(request).list_unassigned_subtasks(story_key)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/users/assignable")
async def assignable_users_(request: Request, project: str = cfg.project, query: str = ""):
    try:
        return await _jira(request).assignable_users(project, query)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/priorities")
async def priorities_(request: Request):
    try:
        return await _jira(request).list_priorities()
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/issues/table")
async def issue_table_(request: Request, project: str = cfg.project,
                       epic: str | None = None, story: str | None = None):
    try:
        return await _jira(request).list_issue_rows(project, epic, story)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/timelog/gantt")
async def timelog_gantt_(request: Request, days: int = 14,
                         epic: str | None = None, story: str | None = None):
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    try:
        return {"since": since,
                "issues": await _jira(request).my_worklog_gantt(since, epic, story)}
    except JiraError as e:
        raise HTTPException(502, e.message) from None


_LEVEL_ISSUE_TYPE = {"epic": "Epic", "story": "Story", "bug": "Bug", "task": "Task", "subtask": "Sub-Task"}


@app.get("/statuses")
async def story_statuses_(request: Request, project: str = cfg.project, level: str = "story"):
    issue_type = _LEVEL_ISSUE_TYPE.get(level, "Story")
    try:
        return await _jira(request).project_story_statuses(project, issue_type)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.post("/issues/{issue_key}/transition")
async def transition_issue_(issue_key: str, body: dict, request: Request):
    target = (body.get("status") or "").strip()
    if not target:
        raise HTTPException(400, "status is required")
    try:
        await _jira(request).transition_to(issue_key, target)
    except JiraError as e:
        raise HTTPException(502, e.message) from None
    return {"key": issue_key, "status": target}


@app.get("/subtasks")
async def list_my_subtasks_(request: Request, project: str = cfg.project):
    try:
        return await _jira(request).list_my_subtasks(project)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/stories/{story_key}/subtasks")
async def list_subtasks_(story_key: str, request: Request):
    try:
        return await _jira(request).get_subtasks(story_key)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/issues/{key}/parents")
async def issue_parents_(key: str, request: Request):
    try:
        return await _jira(request).get_issue_parents(key)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/subtask-types")
async def subtask_types_(request: Request, project: str = cfg.project):
    try:
        return await _jira(request).list_subtask_types(project)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/story-types")
async def story_types_(request: Request, project: str = cfg.project):
    try:
        return await _jira(request).list_story_types(project)
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.post("/story")
async def create_story_(body: StoryCreate, request: Request):
    client = _jira(request)
    account_id = (await client.myself())["accountId"]
    fields: dict = {
        "project": {"key": body.projectKey},
        "issuetype": {"id": body.issueTypeId},
        "summary": body.title,
        "description": text_to_adf(body.description or "-"),
        "assignee": {"id": account_id},
        "reporter": {"id": account_id},
    }
    # Some issue types (e.g. Bug) require "Acceptance Criteria"; same resolution as sub-tasks.
    apply_extra_fields(cfg, fields, {"acceptance": body.acceptance or "-"})
    if body.epicKey:
        fields["parent"] = {"key": body.epicKey}
    if body.startDate:
        start_field = cfg.field_ids.get("Start Date") or getattr(cfg, "start_date_field", "")
        if start_field:
            fields[start_field] = body.startDate
    if body.endDate:
        end_field = getattr(cfg, "end_date_field", "") or "duedate"
        fields[end_field] = body.endDate
    try:
        key = await client.create_issue(fields)
        return {"key": key}
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.get("/link-types")
async def link_types_(request: Request):
    try:
        return await _jira(request).list_link_types()
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.post("/issues/link")
async def link_issues_(body: dict, request: Request):
    """Link two issues. Accepts either:
      { inwardKey, outwardKey, linkType }  — raw type name
      { sourceKey, targetKey, label }      — directional label e.g. 'blocks', 'is blocked by'
    """
    client = _jira(request)
    label = (body.get("label") or "").strip()
    if label:
        source = (body.get("sourceKey") or "").strip()
        target = (body.get("targetKey") or "").strip()
        if not source or not target:
            raise HTTPException(400, "sourceKey and targetKey are required")
        try:
            result = await client.link_issues_by_label(source, target, label)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        except JiraError as e:
            raise HTTPException(502, e.message) from None
        return result
    else:
        inward = (body.get("inwardKey") or "").strip()
        outward = (body.get("outwardKey") or "").strip()
        link_type = (body.get("linkType") or "Relates").strip()
        if not inward or not outward:
            raise HTTPException(400, "inwardKey and outwardKey are required")
        try:
            await client.link_issues(inward, outward, link_type)
        except JiraError as e:
            raise HTTPException(502, e.message) from None
        return {"inwardKey": inward, "outwardKey": outward, "linkType": link_type}


_DASHBOARD_CACHE_TTL = 300
_dashboard_cache: dict[int, tuple[float, dict]] = {}


@app.get("/dashboard")
async def dashboard_(request: Request, weeks: int = 12):
    cached = _dashboard_cache.get(weeks)
    if cached and time.time() - cached[0] < _DASHBOARD_CACHE_TTL:
        return cached[1]
    today = date.today()
    start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
    try:
        totals = await _jira(request).my_worklog_seconds_by_day(start.isoformat())
        counts = await _jira(request).issue_counts()
    except JiraError as e:
        raise HTTPException(502, e.message) from None
    result = {**dashboard.compute(totals, weeks, today), "counts": counts}
    _dashboard_cache[weeks] = (time.time(), result)
    return result


@app.post("/subtask")
async def create_subtask_endpoint(body: SubtaskCreate, request: Request):
    inp = body.model_dump()
    v = validate.validate_create(inp)
    if not v["ok"]:
        raise HTTPException(400, v["errors"])
    try:
        return await runner.run_create(_jira(request), validate.build_create_job(inp))
    except JiraError as e:
        raise HTTPException(502, e.message) from None


@app.post("/timelog")
async def create_timelog_endpoint(body: TimelogCreate, request: Request):
    inp = body.model_dump()
    v = validate.validate_timelog(inp)
    if not v["ok"]:
        raise HTTPException(400, v["errors"])
    try:
        return await runner.run_log(_jira(request), validate.build_log_job(inp))
    except JiraError as e:
        raise HTTPException(502, e.message) from None
