"""Jira Cloud REST API v3 client using httpx.AsyncClient. Basic auth (email + token)."""

import base64

import httpx

from .adf import text_to_adf, adf_to_text
from .jira_fields import apply_extra_fields
from .timeutil import started_iso, duration_to_seconds


class JiraError(Exception):
    """Raised when a Jira API call returns a non-2xx response."""

    def __init__(self, status: int, message: str):
        super().__init__(f"Jira API {status}: {message}")
        self.status = status
        self.message = message


class JiraClient:
    def __init__(self, config):
        self.cfg = config
        token = base64.b64encode(f"{config.email}:{config.api_token}".encode()).decode()
        self._auth = f"Basic {token}"
        self._client = httpx.AsyncClient(base_url=config.base_url, timeout=30)
        self._field_map: dict | None = None

    async def __aenter__(self) -> "JiraClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # ── low-level ───────────────────────────────────────────────────────
    async def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        headers = {"Authorization": self._auth, "Accept": "application/json"}
        try:
            resp = await self._client.request(method, path, json=body, headers=headers)
            resp.raise_for_status()
            return resp.json() if resp.content else {}
        except httpx.HTTPStatusError as e:
            raise JiraError(e.response.status_code, e.response.text) from None
        except httpx.HTTPError as e:
            raise JiraError(0, str(e)) from None

    # ── field metadata ──────────────────────────────────────────────────
    async def field_map(self) -> dict:
        """Cached {lowercase display name: field id} for every field in this Jira instance."""
        if self._field_map is None:
            fields = await self._request("GET", "/rest/api/3/field")
            self._field_map = {f["name"].strip().lower(): f["id"] for f in fields}
        return self._field_map

    async def resolve_fields(self, names: list[str] | None = None) -> dict:
        """Resolve a list of display names to real Jira field ids. Names not found in this
        instance are simply absent from the result — never an error."""
        from .jira_fields import FIELD_NAMES
        fmap = await self.field_map()
        out = {}
        for name in (names or FIELD_NAMES):
            fid = fmap.get(name.strip().lower())
            if fid:
                out[name] = fid
        return out

    # ── API operations ──────────────────────────────────────────────────
    async def myself(self) -> dict:
        return await self._request("GET", "/rest/api/3/myself")

    async def list_projects(self) -> list[dict]:
        """Return [{'key','name'}] of all projects visible to the user (paginated)."""
        out, start = [], 0
        while True:
            page = await self._request("GET", f"/rest/api/3/project/search?maxResults=50&startAt={start}")
            out.extend({"key": p["key"], "name": p["name"]} for p in page.get("values", []))
            if page.get("isLast", True) or not page.get("values"):
                break
            start += len(page["values"])
        return out

    async def list_subtask_types(self, project_key: str) -> list[dict]:
        """Return [{'name','id'}] of sub-task issue types in a project."""
        data = await self._request("GET", f"/rest/api/3/project/{project_key}")
        return [{"name": it["name"], "id": it["id"]}
                for it in data.get("issueTypes", []) if it.get("subtask")]

    async def list_story_types(self, project_key: str) -> list[dict]:
        """Return [{'name','id'}] of non-subtask, non-epic issue types (Story, Task, Bug, etc.)."""
        data = await self._request("GET", f"/rest/api/3/project/{project_key}")
        return [{"name": it["name"], "id": it["id"]}
                for it in data.get("issueTypes", [])
                if not it.get("subtask") and it.get("name", "").lower() != "epic"]

    async def create_subtask(self, job: dict, account_id: str) -> str:
        """Create a subtask under job['storyKey']; return the new issue key."""
        cfg = self.cfg
        project_key = job.get("projectKey") or job["storyKey"].split("-")[0]
        fields = {
            "project": {"key": project_key},
            "parent": {"key": job["storyKey"]},
            "summary": job["title"],
            "description": text_to_adf(job["description"]),
            "assignee": {"id": account_id},
            "reporter": {"id": account_id},
        }
        type_id = job.get("issueTypeId") or cfg.subtask_type_id
        fields["issuetype"] = {"id": type_id} if type_id else {"name": "Sub-task"}
        apply_extra_fields(cfg, fields, {
            "acceptance": job.get("acceptance", "-"),
            "labels": job.get("labels"),
            "sprint": job.get("sprint"),
        })
        start_field = cfg.field_ids.get("Start Date") or getattr(cfg, "start_date_field", "")
        if start_field and job.get("startDate"):
            fields[start_field] = job["startDate"]
        end_field = getattr(cfg, "end_date_field", "") or "duedate"
        if job.get("endDate"):
            fields[end_field] = job["endDate"]
        result = await self._request("POST", "/rest/api/3/issue", {"fields": fields})
        return result["key"]

    async def get_subtasks(self, issue_key: str) -> list[dict]:
        """Return [{'key','summary','status'}] of a story's existing subtasks."""
        data = await self._request("GET", f"/rest/api/3/issue/{issue_key}?fields=subtasks")
        out = []
        for s in data.get("fields", {}).get("subtasks", []):
            f = s.get("fields", {})
            out.append({"key": s["key"], "summary": f.get("summary", ""),
                        "status": f.get("status", {}).get("name", ""),
                        "type": f.get("issuetype", {}).get("name", "")})
        return out

    async def list_my_subtasks(self, project_key: str) -> list[dict]:
        """Open subtasks/tasks assigned to current user in project."""
        return await self._search_summaries(
            f"project = {project_key} "
            f"AND issuetype in subtaskIssueTypes() "
            f"AND assignee = currentUser() AND statusCategory != Done "
            f"ORDER BY updated DESC")

    async def get_issue_parents(self, issue_key: str) -> dict:
        """Return {story_key, epic_key, epic_summary, epic_status} for a subtask;
        {epic_key, epic_summary, epic_status} for a story."""
        data = await self._request("GET", f"/rest/api/3/issue/{issue_key}?fields=parent,issuetype")
        fields = data.get("fields", {})
        parent = fields.get("parent", {})
        parent_key = parent.get("key")
        is_subtask = fields.get("issuetype", {}).get("subtask", False)
        result: dict = {"story_key": None, "epic_key": None, "epic_summary": None, "epic_status": None}
        if is_subtask:
            result["story_key"] = parent_key
            if parent_key:
                story = await self._request(
                    "GET", f"/rest/api/3/issue/{parent_key}?fields=parent,summary,status")
                sf = story.get("fields", {})
                epic_key = sf.get("parent", {}).get("key")
                result["epic_key"] = epic_key
                result["story_summary"] = sf.get("summary", "")
                result["story_status"] = sf.get("status", {}).get("name", "")
                if epic_key:
                    epic = await self._request(
                        "GET", f"/rest/api/3/issue/{epic_key}?fields=summary,status")
                    ef = epic.get("fields", {})
                    result["epic_summary"] = ef.get("summary", "")
                    result["epic_status"] = ef.get("status", {}).get("name", "")
        else:
            result["epic_key"] = parent_key
            if parent_key:
                epic = await self._request(
                    "GET", f"/rest/api/3/issue/{parent_key}?fields=summary,status")
                ef = epic.get("fields", {})
                result["epic_summary"] = ef.get("summary", "")
                result["epic_status"] = ef.get("status", {}).get("name", "")
        return result

    async def set_due_date(self, issue_key: str, due_date: str, field: str = "duedate") -> None:
        """Update a single date field on an existing issue."""
        await self._request("PUT", f"/rest/api/3/issue/{issue_key}", {"fields": {field: due_date}})

    async def update_issue(self, key: str, fields: dict) -> None:
        """Update arbitrary fields on an existing issue (used by edit-mode requests)."""
        await self._request("PUT", f"/rest/api/3/issue/{key}", {"fields": fields})

    async def search_issue_keys(self, jql: str, limit: int = 200) -> list[str]:
        """Return issue keys matching a JQL query (paginated via nextPageToken)."""
        import urllib.parse
        keys, token = [], None
        while len(keys) < limit:
            q = {"jql": jql, "maxResults": "100", "fields": "key"}
            if token:
                q["nextPageToken"] = token
            page = await self._request("GET", "/rest/api/3/search/jql?" + urllib.parse.urlencode(q))
            keys.extend(i["key"] for i in page.get("issues", []))
            token = page.get("nextPageToken")
            if not token:
                break
        return keys

    async def _search_summaries(self, jql: str, limit: int = 100) -> list[dict]:
        import urllib.parse
        out, token = [], None
        while len(out) < limit:
            q = {"jql": jql, "maxResults": "100", "fields": "summary,status,issuetype"}
            if token:
                q["nextPageToken"] = token
            page = await self._request("GET", "/rest/api/3/search/jql?" + urllib.parse.urlencode(q))
            for i in page.get("issues", []):
                f = i.get("fields", {})
                out.append({"key": i["key"], "summary": f.get("summary", ""),
                            "status": f.get("status", {}).get("name", "")})
            token = page.get("nextPageToken")
            if not token:
                break
        return out

    async def search_with_fields(self, jql: str, limit: int = 15) -> list[dict]:
        """Like _search_summaries but ALSO returns description + acceptance-criteria text, for
        up to `limit` issues in ONE call. Use for bulk cross-ticket analysis instead of looping
        single-issue fetches — one API round trip regardless of how many issues match."""
        import urllib.parse
        acc_id = self.cfg.field_ids.get("Acceptance Criteria") or getattr(self.cfg, "acceptance_field", "") or ""
        fields = "summary,issuetype,status,description" + (f",{acc_id}" if acc_id else "")
        q = {"jql": jql, "maxResults": str(limit), "fields": fields}
        page = await self._request("GET", "/rest/api/3/search/jql?" + urllib.parse.urlencode(q))
        out = []
        for i in page.get("issues", []):
            f = i.get("fields", {})
            out.append({
                "key": i["key"],
                "summary": f.get("summary", ""),
                "type": f.get("issuetype", {}).get("name", ""),
                "status": f.get("status", {}).get("name", ""),
                "description": adf_to_text(f.get("description")),
                "acceptance": adf_to_text(f.get(acc_id)) if acc_id else "",
            })
        return out

    async def list_epics(self, project_key: str) -> list[dict]:
        return await self._search_summaries(
            f"project = {project_key} AND issuetype = Epic ORDER BY created DESC")

    async def list_stories(self, epic_key: str) -> list[dict]:
        return await self._search_summaries(
            f"parent = {epic_key} AND issuetype = Story ORDER BY created DESC")

    async def list_bugs(self, epic_key: str) -> list[dict]:
        return await self._search_summaries(
            f"parent = {epic_key} AND issuetype = Bug ORDER BY created DESC")

    async def list_tasks(self, epic_key: str) -> list[dict]:
        return await self._search_summaries(
            f"parent = {epic_key} AND issuetype = Task ORDER BY created DESC")

    async def list_project_bugs(self, project_key: str) -> list[dict]:
        return await self._search_summaries(
            f"project = {project_key} AND issuetype = Bug AND "
            f"assignee = currentUser() ORDER BY created DESC")

    async def list_project_tasks(self, project_key: str) -> list[dict]:
        return await self._search_summaries(
            f"project = {project_key} AND issuetype = Task AND "
            f"assignee = currentUser() ORDER BY created DESC")

    async def list_unassigned_stories(self, project_key: str, epic_key: str = "") -> list[dict]:
        if epic_key:
            return await self._search_summaries(
                f"parent = {epic_key} AND issuetype = Story AND assignee is EMPTY ORDER BY created DESC")
        return await self._search_summaries(
            f"project = {project_key} AND issuetype = Story AND assignee is EMPTY ORDER BY created DESC")

    async def list_unassigned_bugs(self, project_key: str, epic_key: str = "") -> list[dict]:
        if epic_key:
            return await self._search_summaries(
                f"parent = {epic_key} AND issuetype = Bug AND assignee is EMPTY ORDER BY created DESC")
        return await self._search_summaries(
            f"project = {project_key} AND issuetype = Bug AND assignee is EMPTY ORDER BY created DESC")

    async def list_unassigned_tasks(self, project_key: str, epic_key: str = "") -> list[dict]:
        if epic_key:
            return await self._search_summaries(
                f"parent = {epic_key} AND issuetype = Task AND assignee is EMPTY ORDER BY created DESC")
        return await self._search_summaries(
            f"project = {project_key} AND issuetype = Task AND assignee is EMPTY ORDER BY created DESC")

    async def list_unassigned_epics(self, project_key: str) -> list[dict]:
        return await self._search_summaries(
            f"project = {project_key} AND issuetype = Epic AND assignee is EMPTY ORDER BY created DESC")

    async def list_unassigned_subtasks(self, story_key: str) -> list[dict]:
        return await self._search_summaries(
            f"parent = {story_key} AND issuetype in subtaskIssueTypes() AND assignee is EMPTY ORDER BY created DESC")

    async def list_project_unassigned_subtasks(self, project_key: str) -> list[dict]:
        return await self._search_summaries(
            f"project = {project_key} AND issuetype in subtaskIssueTypes() AND assignee is EMPTY ORDER BY updated DESC")

    async def list_project_stories(self, project_key: str) -> list[dict]:
        """The current user's stories in a project regardless of parent epic — for pickers
        where the user doesn't want to drill through the epic first.
        Uses two standard JQL queries (no ScriptRunner) to include stories that have
        subtasks assigned to the current user even when the story itself is not."""
        import urllib.parse
        # Step 1: stories directly assigned to me
        mine = await self._search_summaries(
            f"project = {project_key} AND issuetype in (Story, Bug, Task) AND "
            f"assignee = currentUser() ORDER BY created DESC")
        # Step 2: parent story keys of my subtasks
        q = {
            "jql": (f"project = {project_key} AND issuetype in subtaskIssueTypes() "
                    f"AND assignee = currentUser()"),
            "maxResults": "200",
            "fields": "parent",
        }
        page = await self._request("GET", "/rest/api/3/search/jql?" + urllib.parse.urlencode(q))
        parent_keys = list({
            i["fields"]["parent"]["key"]
            for i in page.get("issues", [])
            if i.get("fields", {}).get("parent", {}).get("key")
        })
        seen = {s["key"] for s in mine}
        missing = [k for k in parent_keys if k not in seen]
        if missing:
            extra = await self._search_summaries(
                f"key in ({', '.join(missing)}) AND issuetype in (Story, Bug, Task) "
                f"ORDER BY created DESC")
            return list(mine) + extra
        return mine

    async def list_issue_rows(self, project_key: str, epic_key: str | None = None,
                              story_key: str | None = None) -> list[dict]:
        """Jira-board-style drill-down rows (work/priority/story points/assignee/status):
        story given -> its sub-tasks; epic given -> the user's stories under it; neither ->
        the user's assigned epics in the project. Story Points id resolved dynamically by
        name (never hardcoded customfield_NNNNN)."""
        import urllib.parse
        fmap = await self.field_map()
        sp_id = fmap.get("story points") or fmap.get("story point estimate") or ""
        if story_key:
            jql = f"parent = {story_key} ORDER BY created DESC"
        elif epic_key:
            jql = (f"parent = {epic_key} AND issuetype = Story AND "
                   "assignee = currentUser() ORDER BY created DESC")
        else:
            jql = (f"project = {project_key} AND issuetype = Epic AND "
                   "assignee = currentUser() ORDER BY created DESC")
        start_id = fmap.get("start date") or self.cfg.start_date_field or ""
        fields = ("summary,priority,assignee,status,issuetype,duedate"
                  + (f",{sp_id}" if sp_id else "") + (f",{start_id}" if start_id else ""))
        q = {"jql": jql, "maxResults": "100", "fields": fields}
        page = await self._request("GET", "/rest/api/3/search/jql?" + urllib.parse.urlencode(q))
        out = []
        for i in page.get("issues", []):
            f = i.get("fields", {})
            out.append({
                "key": i["key"],
                "summary": f.get("summary", ""),
                "priority": (f.get("priority") or {}).get("name", ""),
                "story_points": f.get(sp_id) if sp_id else None,
                "assignee": (f.get("assignee") or {}).get("displayName", ""),
                "status": (f.get("status") or {}).get("name", ""),
                "issue_type": (f.get("issuetype") or {}).get("name", ""),
                "start_date": f.get(start_id) if start_id else None,
                "due_date": f.get("duedate"),
            })
        return out

    async def my_worklog_gantt(self, since_date: str, epic_key: str | None = None,
                               story_key: str | None = None) -> list[dict]:
        """Per-issue, per-day seconds the current user logged since a date — for the
        timelog gantt. Same author-filter logic as my_worklog_seconds_by_day, but kept
        per issue instead of flattened. Optional drill-down scope: story -> that story's
        sub-tasks (and the story itself); epic -> everything under the epic (parentEpic)."""
        me = (await self.myself()).get("accountId", "")
        scope = ""
        if story_key:
            scope = f" AND (parent = {story_key} OR issuekey = {story_key})"
        elif epic_key:
            scope = f" AND parentEpic = {epic_key}"
        jql = (f'worklogAuthor = currentUser() AND worklogDate >= "{since_date}"{scope} '
               "ORDER BY created DESC")
        out = []
        for issue in await self._search_summaries(jql):
            days: dict[str, int] = {}
            for w in await self.get_worklogs(issue["key"]):
                day = (w["started"] or "")[:10]
                if w["author"] == me and day >= since_date:
                    days[day] = days.get(day, 0) + w["seconds"]
            if days:
                out.append({"key": issue["key"], "summary": issue["summary"], "days": days})
        return out

    async def project_story_statuses(self, project_key: str, issue_type: str = "Story") -> list[str]:
        """Distinct status names available to a given issue type in a project — dynamic,
        for status dropdowns. Falls back to the union across all issue types if not found."""
        data = await self._request("GET", f"/rest/api/3/project/{project_key}/statuses")
        for itype in data if isinstance(data, list) else []:
            if itype.get("name") == issue_type:
                return [s["name"] for s in itype.get("statuses", [])]
        seen: list[str] = []
        for itype in data if isinstance(data, list) else []:
            for s in itype.get("statuses", []):
                if s["name"] not in seen:
                    seen.append(s["name"])
        return seen

    async def create_issue(self, fields: dict) -> str:
        """Create any issue from a fully-built fields dict; return the new key."""
        result = await self._request("POST", "/rest/api/3/issue", {"fields": fields})
        return result["key"]

    async def count(self, jql: str) -> int:
        """Approximate count of issues matching a JQL query."""
        r = await self._request("POST", "/rest/api/3/search/approximate-count", {"jql": jql})
        return r.get("count", 0)

    async def issue_counts(self) -> dict:
        """Counts of the current user's open/closed stories and subtasks."""
        me = "assignee = currentUser()"
        return {
            "open_stories": await self.count(f"{me} AND issuetype = Story AND statusCategory != Done"),
            "closed_stories": await self.count(f"{me} AND issuetype = Story AND statusCategory = Done"),
            "open_subtasks": await self.count(f"{me} AND issuetype in subtaskIssueTypes() AND statusCategory != Done"),
            "closed_subtasks": await self.count(f"{me} AND issuetype in subtaskIssueTypes() AND statusCategory = Done"),
        }

    async def get_worklogs(self, issue_key: str) -> list[dict]:
        """Return [{'author','started','seconds'}] for an issue's worklogs."""
        data = await self._request("GET", f"/rest/api/3/issue/{issue_key}/worklog")
        return [{"author": w.get("author", {}).get("accountId", ""),
                 "started": w.get("started", ""),
                 "seconds": w.get("timeSpentSeconds", 0)} for w in data.get("worklogs", [])]

    async def my_worklog_seconds_by_day(self, since_date: str) -> dict:
        """Sum the current user's logged seconds per day (YYYY-MM-DD) since a date."""
        me = (await self.myself()).get("accountId", "")
        jql = f'worklogAuthor = currentUser() AND worklogDate >= "{since_date}"'
        totals: dict[str, int] = {}
        for key in await self.search_issue_keys(jql):
            for w in await self.get_worklogs(key):
                day = (w["started"] or "")[:10]
                if w["author"] == me and day >= since_date:
                    totals[day] = totals.get(day, 0) + w["seconds"]
        return totals

    async def get_transitions(self, issue_key: str) -> list[dict]:
        data = await self._request("GET", f"/rest/api/3/issue/{issue_key}/transitions")
        return data.get("transitions", [])

    async def transition_to(self, issue_key: str, target_name: str) -> None:
        """Transition an issue toward a status. Matches either the transition name OR the
        destination status name, case-insensitive (workflows name these inconsistently)."""
        target = target_name.strip().lower()
        transitions = await self.get_transitions(issue_key)
        for t in transitions:
            names = {t["name"].strip().lower(), t.get("to", {}).get("name", "").strip().lower()}
            if target in names:
                await self._request("POST", f"/rest/api/3/issue/{issue_key}/transitions",
                                    {"transition": {"id": t["id"]}})
                return
        avail = ", ".join(f'{t["name"]}->{t.get("to", {}).get("name", "?")}' for t in transitions)
        raise JiraError(0, f'No transition to "{target_name}" on {issue_key}. Available: {avail}')

    async def list_link_types(self) -> list[dict]:
        data = await self._request("GET", "/rest/api/3/issueLinkType")
        return [{"id": t["id"], "name": t["name"],
                 "inward": t["inward"], "outward": t["outward"]}
                for t in data.get("issueLinkTypes", [])]

    async def link_issues(self, inward_key: str, outward_key: str, link_type: str = "Relates") -> None:
        """Create an issue link. link_type = link type name e.g. 'Blocks', 'Relates', 'Cloners'."""
        await self._request("POST", "/rest/api/3/issueLink", {
            "type": {"name": link_type},
            "inwardIssue": {"key": inward_key},
            "outwardIssue": {"key": outward_key},
        })

    async def link_issues_by_label(self, source_key: str, target_key: str, label: str) -> dict:
        """Link two issues using a directional label like 'blocks' or 'is blocked by'.
        Resolves label → link type, swaps inward/outward as needed."""
        types = await self.list_link_types()
        label_lower = label.strip().lower()
        for t in types:
            if t["outward"].lower() == label_lower:
                # source is the outward issue (e.g. "blocks")
                await self._request("POST", "/rest/api/3/issueLink", {
                    "type": {"name": t["name"]},
                    "inwardIssue": {"key": target_key},
                    "outwardIssue": {"key": source_key},
                })
                return {"typeName": t["name"], "label": label, "inwardKey": target_key, "outwardKey": source_key}
            if t["inward"].lower() == label_lower:
                # source is the inward issue (e.g. "is blocked by")
                await self._request("POST", "/rest/api/3/issueLink", {
                    "type": {"name": t["name"]},
                    "inwardIssue": {"key": source_key},
                    "outwardIssue": {"key": target_key},
                })
                return {"typeName": t["name"], "label": label, "inwardKey": source_key, "outwardKey": target_key}
        raise ValueError(f"Unknown link label: {label!r}")

    async def add_worklog(self, issue_key: str, worklog: dict, tz_offset: str = "+0000") -> dict:
        """Add a native worklog. started = endTime - timeSpent."""
        body = {
            "started": started_iso(worklog["date"], worklog["endTime"], worklog["timeSpent"], tz_offset),
            "timeSpentSeconds": duration_to_seconds(worklog["timeSpent"]),
        }
        if worklog.get("description"):
            body["comment"] = text_to_adf(worklog["description"])
        return await self._request("POST", f"/rest/api/3/issue/{issue_key}/worklog", body)
