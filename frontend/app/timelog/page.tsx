"use client";

import { useEffect, useState } from "react";
import { api, ApiError, ProjectSummary, RunResult } from "@/lib/api";
import { useToast } from "@/components/Toast";
import GanttTabs from "@/components/TimelogGantt";
import CreateIssueDialog from "@/components/CreateIssueDialog";
import LinkIssueDialog from "@/components/LinkIssueDialog";

interface IssueSummary {
  key: string;
  summary: string;
  status: string;
}

interface ParentInfo {
  story_key: string | null;
  epic_key: string | null;
  epic_summary: string | null;
  epic_status: string | null;
  story_summary?: string | null;
  story_status?: string | null;
}

interface IssueRow {
  key: string;
  summary: string;
  priority: string;
  story_points: number | null;
  assignee: string;
  status: string;
  issue_type: string;
  start_date: string | null;
  due_date: string | null;
}

const inputCls =
  "w-full rounded-lg border border-line bg-surface2 px-3 py-2 text-sm text-ink outline-none focus:border-brand";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm text-muted">
      {label}
      {children}
    </label>
  );
}

export default function TimelogPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [projectKey, setProjectKey] = useState("");
  const [epics, setEpics] = useState<IssueSummary[]>([]);
  const [epicKey, setEpicKey] = useState("");
  const [stories, setStories] = useState<IssueSummary[]>([]);
  const [storyKey, setStoryKey] = useState("");
  const [subtasks, setSubtasks] = useState<IssueSummary[]>([]);
  const [subtaskKey, setSubtaskKey] = useState("");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [timeSpent, setTimeSpent] = useState("");
  const [endTime, setEndTime] = useState("");
  const [description, setDescription] = useState("");
  const [close, setClose] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [rows, setRows] = useState<IssueRow[]>([]);
  const [createDialog, setCreateDialog] = useState<"story" | "subtask" | null>(null);
  const [linkDialog, setLinkDialog] = useState<string | null>(null); // null = closed, "" = no pre-fill, "WAR-123" = pre-filled

  const [rowsRefresh, setRowsRefresh] = useState(0);
  const [ganttRefresh, setGanttRefresh] = useState(0);

  const [statuses, setStatuses] = useState<string[]>([]);
  const [epicStatuses, setEpicStatuses] = useState<string[]>([]);
  const [storyStatuses, setStoryStatuses] = useState<string[]>([]);
  const [bugStatuses, setBugStatuses] = useState<string[]>([]);
  const [taskStatuses, setTaskStatuses] = useState<string[]>([]);
  const [transitioning, setTransitioning] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    api.get<{ default_project: string }>("/config").then(({ default_project }) => {
      setProjectKey(default_project);
      api
        .get<ProjectSummary[]>("/projects")
        .then((ps) => {
          setProjects(ps);
          if (ps.length > 0 && !ps.some((p) => p.key === default_project)) setProjectKey(ps[0].key);
        })
        .catch(() => setProjects([]));
    }).catch(() => {
      api
        .get<ProjectSummary[]>("/projects")
        .then((ps) => {
          setProjects(ps);
          if (ps.length > 0) setProjectKey(ps[0].key);
        })
        .catch(() => setProjects([]));
    });
    api.get<IssueSummary[]>("/epics?open_only=true&mine=true").then(setEpics).catch(() => setEpics([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load stories when epic or project changes (no cascading resets — handlers do that)
  useEffect(() => {
    const url = epicKey ? `/epics/${epicKey}/stories` : `/stories?project=${projectKey}`;
    api.get<IssueSummary[]>(url).then(setStories).catch(() => setStories([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [epicKey, projectKey]);

  // Load subtasks: all mine when no story selected, else story's subtasks
  useEffect(() => {
    const url = storyKey
      ? `/stories/${storyKey}/subtasks`
      : `/subtasks?project=${projectKey}`;
    api.get<IssueSummary[]>(url).then(setSubtasks).catch(() => setSubtasks([]));
  }, [storyKey, projectKey]);

  // Load table rows when selection or rowsRefresh changes
  useEffect(() => {
    const params = new URLSearchParams({ project: projectKey });
    if (epicKey) params.set("epic", epicKey);
    if (storyKey) params.set("story", storyKey);
    api.get<IssueRow[]>(`/issues/table?${params}`).then(setRows).catch(() => setRows([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [epicKey, storyKey, projectKey, rowsRefresh]);

  const level: "epic" | "story" | "subtask" = storyKey ? "subtask" : epicKey ? "story" : "epic";

  useEffect(() => {
    api.get<string[]>(`/statuses?project=${projectKey}&level=${level}`)
      .then(setStatuses)
      .catch(() => setStatuses([]));
  }, [projectKey, level]);


  useEffect(() => {
    api.get<string[]>(`/statuses?project=${projectKey}&level=epic`)
      .then(setEpicStatuses)
      .catch(() => setEpicStatuses([]));
    api.get<string[]>(`/statuses?project=${projectKey}&level=story`)
      .then(setStoryStatuses)
      .catch(() => setStoryStatuses([]));
    api.get<string[]>(`/statuses?project=${projectKey}&level=bug`)
      .then(setBugStatuses)
      .catch(() => setBugStatuses([]));
    api.get<string[]>(`/statuses?project=${projectKey}&level=task`)
      .then(setTaskStatuses)
      .catch(() => setTaskStatuses([]));
  }, [projectKey]);

  const onProjectChange = (k: string) => {
    setProjectKey(k);
    setEpicKey("");
    setStoryKey("");
    setSubtaskKey("");
  };

  const onEpicChange = (k: string) => {
    setEpicKey(k);
    setStoryKey("");
    setSubtaskKey("");
  };

  const onStoryChange = async (k: string) => {
    setStoryKey(k);
    setSubtaskKey("");
    if (k) {
      try {
        const parents = await api.get<ParentInfo>(`/issues/${k}/parents`);
        if (parents.epic_key) {
          setEpicKey(parents.epic_key);
          setEpics((prev) => {
            if (prev.some((e) => e.key === parents.epic_key)) return prev;
            return [
              { key: parents.epic_key!, summary: parents.epic_summary ?? parents.epic_key!, status: parents.epic_status ?? "" },
              ...prev,
            ];
          });
        }
      } catch {}
    }
  };

  const onSubtaskChange = async (k: string) => {
    setSubtaskKey(k);
    if (!k) return;
    try {
      const parents = await api.get<ParentInfo>(`/issues/${k}/parents`);
      if (parents.story_key) {
        setStoryKey(parents.story_key);
        setStories((prev) => {
          if (prev.some((s) => s.key === parents.story_key)) return prev;
          return [
            { key: parents.story_key!, summary: parents.story_summary ?? parents.story_key!, status: parents.story_status ?? "" },
            ...prev,
          ];
        });
      }
      if (parents.epic_key) {
        setEpicKey(parents.epic_key);
        setEpics((prev) => {
          if (prev.some((e) => e.key === parents.epic_key)) return prev;
          return [
            { key: parents.epic_key!, summary: parents.epic_summary ?? parents.epic_key!, status: parents.epic_status ?? "" },
            ...prev,
          ];
        });
      }
    } catch {}
  };

  const changeStatus = async (key: string, status: string) => {
    setTransitioning(key);
    const prevRows = rows;
    const prevEpics = epics;
    const prevStories = stories;
    setRows((r) => r.map((row) => (row.key === key ? { ...row, status } : row)));
    setEpics((e) => e.map((ep) => (ep.key === key ? { ...ep, status } : ep)));
    setStories((s) => s.map((st) => (st.key === key ? { ...st, status } : st)));
    try {
      await api.post(`/issues/${key}/transition`, { status });
      toast("success", `${key} → ${status}`);
    } catch (e) {
      setRows(prevRows);
      setEpics(prevEpics);
      setStories(prevStories);
      toast("error", e instanceof ApiError ? String(e.detail ?? e) : String(e));
    } finally {
      setTransitioning(null);
    }
  };

  const rowClick = (row: IssueRow) => {
    if (level === "epic") onEpicChange(row.key);
    else if (level === "story") { setStoryKey(row.key); setSubtaskKey(""); }
    else setSubtaskKey(subtaskKey === row.key ? "" : row.key);
  };

  const tableLabel =
    level === "epic"
      ? "Your epics — click one to see its stories"
      : level === "story"
        ? `Your stories under ${epicKey} — click one to see its sub-tasks`
        : `Sub-tasks under ${storyKey} — select one to log time`;

  const submit = async () => {
    const body = { subtaskKey, date, timeSpent, endTime, description, close };
    setSubmitting(true);
    try {
      const r = await api.post<RunResult>("/timelog", body);
      const failed = r.steps.filter((s) => s.status !== "ok");
      if (r.status === "done" && failed.length === 0) {
        toast("success", `Time logged on ${subtaskKey}${close ? " · closed" : ""}`);
        setGanttRefresh((n) => n + 1);
        setTimeout(() => setGanttRefresh((n) => n + 1), 2000);
        if (close) {
          setRowsRefresh((n) => n + 1);
          setTimeout(() => setRowsRefresh((n) => n + 1), 2000);
        }
      } else {
        toast("error", failed.map((s) => `${s.label}: ${s.msg || "failed"}`).join("\n") || "Log failed");
      }
    } catch (e) {
      if (e instanceof ApiError && Array.isArray(e.detail)) {
        toast("error", (e.detail as string[]).join("\n"));
      } else {
        toast("error", String(e));
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-[5rem_1fr_1fr_1fr] gap-4">
        <Field label="Project">
          <select value={projectKey} onChange={(e) => onProjectChange(e.target.value)} className={inputCls}>
            {(projects.length ? projects.map((p) => p.key) : [projectKey]).map((k) => (
              <option key={k} value={k}>{k}</option>
            ))}
          </select>
        </Field>
        <Field label="Epic (optional)">
          <select value={epicKey} onChange={(e) => onEpicChange(e.target.value)} className={inputCls}>
            <option value="">— pick an epic —</option>
            {epics.map((e) => (
              <option key={e.key} value={e.key}>{e.key} — {e.summary.slice(0, 50)}</option>
            ))}
          </select>
          {epicKey && (
            <select
              value={epics.find((e) => e.key === epicKey)?.status ?? ""}
              onChange={(ev) => changeStatus(epicKey, ev.target.value)}
              disabled={transitioning === epicKey}
              className="w-fit rounded-lg border border-line bg-surface2 px-3 py-2 text-sm text-ink outline-none focus:border-brand disabled:opacity-50"
            >
              {(() => {
                const cur = epics.find((e) => e.key === epicKey)?.status ?? "";
                const opts = epicStatuses.includes(cur) ? epicStatuses : [cur, ...epicStatuses];
                return opts.map((st) => <option key={st} value={st}>{st}</option>);
              })()}
            </select>
          )}
        </Field>
        <div className="flex flex-col gap-1 text-sm text-muted">
          <span className="flex items-center justify-between">
            Story / Bug / Task (optional)
            <span className="flex items-center gap-1">
              <button
                onClick={() => setLinkDialog(storyKey || "")}
                className="flex items-center justify-center w-5 h-5 rounded text-muted hover:text-brand hover:bg-surface2 text-sm leading-none"
                title="Link issues"
              >
                ⇌
              </button>
              <button
                onClick={() => setCreateDialog("story")}
                className="flex items-center justify-center w-5 h-5 rounded text-brand hover:bg-surface2 font-bold text-base leading-none"
                title="Create Story / Bug / Task"
              >
                +
              </button>
            </span>
          </span>
          <select
            value={storyKey}
            onChange={(e) => onStoryChange(e.target.value)}
            className={inputCls}
          >
            <option value="">— pick a story / task —</option>
            {stories.map((s) => (
              <option key={s.key} value={s.key}>{s.key} — {s.summary.slice(0, 50)}</option>
            ))}
          </select>
          {storyKey && (
            <select
              value={stories.find((s) => s.key === storyKey)?.status ?? ""}
              onChange={(ev) => changeStatus(storyKey, ev.target.value)}
              disabled={transitioning === storyKey}
              className="w-fit rounded-lg border border-line bg-surface2 px-3 py-2 text-sm text-ink outline-none focus:border-brand disabled:opacity-50"
            >
              {(() => {
                const cur = stories.find((s) => s.key === storyKey)?.status ?? "";
                const opts = storyStatuses.includes(cur) ? storyStatuses : [cur, ...storyStatuses];
                return opts.map((st) => <option key={st} value={st}>{st}</option>);
              })()}
            </select>
          )}
        </div>
        <div className="flex flex-col gap-1 text-sm text-muted">
          <span className="flex items-center justify-between">
            Subtask
            {storyKey && (
              <button
                onClick={() => setCreateDialog("subtask")}
                className="flex items-center justify-center w-5 h-5 rounded text-brand hover:bg-surface2 font-bold text-base leading-none"
                title="Create Subtask"
              >
                +
              </button>
            )}
          </span>
          <select
            value={subtaskKey}
            onChange={(e) => onSubtaskChange(e.target.value)}
            className={inputCls}
          >
            <option value="">— pick a subtask —</option>
            {!subtasks.some((s) => s.key === subtaskKey) && subtaskKey && (
              <option value={subtaskKey}>{subtaskKey}</option>
            )}
            {subtasks.map((s) => (
              <option key={s.key} value={s.key}>{s.key} — {s.summary.slice(0, 60)}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-muted">{tableLabel}</p>
        </div>
        {rows.length === 0 ? (
          <p className="text-xs text-muted">Nothing here.</p>
        ) : (
          <div className="overflow-x-auto overflow-y-auto max-h-[248px] rounded-xl border border-line">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10">
                <tr className="border-b border-line bg-surface text-left text-xs uppercase text-muted">
                  <th className="px-3 py-2 font-semibold">Work</th>
                  <th className="px-3 py-2 font-semibold">Priority</th>
                  <th className="px-3 py-2 font-semibold">Story Points</th>
                  <th className="px-3 py-2 font-semibold">Assignee</th>
                  <th className="px-3 py-2 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.key}
                    className={`border-b border-line/60 last:border-0 hover:bg-surface2/50 cursor-pointer ${
                      level === "subtask" && subtaskKey === row.key
                        ? "bg-surface2 outline outline-1 outline-brand -outline-offset-1"
                        : ""
                    }`}
                    onClick={() => rowClick(row)}
                  >
                    <td className="px-3 py-2 text-ink">
                      <span className="font-medium text-brand">{row.key}</span>
                      <span className="text-muted"> — {row.summary.slice(0, 60)}</span>
                    </td>
                    <td className="px-3 py-2 text-ink">{row.priority || "—"}</td>
                    <td className="px-3 py-2 text-ink">{row.story_points ?? "—"}</td>
                    <td className="px-3 py-2 text-ink">{row.assignee || "—"}</td>
                    <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                      {(() => {
                        const t = row.issue_type?.toLowerCase() ?? "";
                        const rowStatuses =
                          t === "bug" ? bugStatuses
                          : t === "task" ? taskStatuses
                          : t === "story" ? storyStatuses
                          : statuses;
                        return (
                          <select
                            value={row.status}
                            onChange={(e) => changeStatus(row.key, e.target.value)}
                            disabled={transitioning === row.key}
                            className="rounded-lg border border-line bg-surface2 px-2 py-1 text-xs text-ink outline-none focus:border-brand disabled:opacity-50"
                          >
                            {!rowStatuses.includes(row.status) && (
                              <option value={row.status}>{row.status}</option>
                            )}
                            {rowStatuses.map((st) => (
                              <option key={st} value={st}>{st}</option>
                            ))}
                          </select>
                        );
                      })()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {subtaskKey && (
        <p className="text-sm text-brand">Logging time on {subtaskKey}</p>
      )}

      <div className="grid grid-cols-4 gap-4">
        <Field label="Date">
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputCls} />
        </Field>
        <Field label="Time spent">
          <input value={timeSpent} onChange={(e) => setTimeSpent(e.target.value)} placeholder="2h 30m" className={inputCls} />
        </Field>
        <Field label="End time">
          <input value={endTime} onChange={(e) => setEndTime(e.target.value)} placeholder="17:00" className={inputCls} />
        </Field>
        <Field label="Description">
          <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What did you work on?" className={inputCls} />
        </Field>
      </div>

      <label className="flex items-center gap-2 text-sm text-ink">
        <input type="checkbox" checked={close} onChange={(e) => setClose(e.target.checked)} />
        Close subtask after logging
      </label>

      <button
        onClick={submit}
        disabled={submitting || !subtaskKey || !timeSpent.trim() || !endTime.trim()}
        suppressHydrationWarning
        className="self-start rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        {submitting ? "Working…" : "Log Time"}
      </button>

      <GanttTabs rows={rows} ganttRefresh={ganttRefresh} />

      {linkDialog !== null && (
        <LinkIssueDialog
          defaultKey={linkDialog}
          onClose={() => setLinkDialog(null)}
        />
      )}

      {createDialog && (
        <CreateIssueDialog
          mode={createDialog}
          projectKey={projectKey}
          epicKey={epicKey}
          storyKey={storyKey}
          onClose={() => setCreateDialog(null)}
          onCreated={(key, summary, hasWorklogs) => {
            if (createDialog === "story") {
              setStories((prev) => [{ key, summary, status: "" }, ...prev]);
              onStoryChange(key);
            }
            setRowsRefresh((n) => n + 1);
            setTimeout(() => setRowsRefresh((n) => n + 1), 2000);
            if (hasWorklogs) {
              setGanttRefresh((n) => n + 1);
              setTimeout(() => setGanttRefresh((n) => n + 1), 2000);
            }
          }}
        />
      )}
    </div>
  );
}
