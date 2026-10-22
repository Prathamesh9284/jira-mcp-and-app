const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text();
    }
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? (body as { detail: unknown }).detail
        : body;
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export interface HealthResponse {
  jira: boolean;
  llm: boolean;
  missing: string[];
}

export interface ProjectSummary {
  key: string;
  name: string;
}

export interface SubtaskType {
  name: string;
  id: string;
}

export interface IssueType {
  name: string;
  id: string;
}

export interface KbDocSummary {
  name: string;
  path: string;
}

export interface KbDocContent {
  content: string;
}

export interface DashboardDay {
  date: string;
  week_start: string;
  weekday_name: string;
  hours: number;
  logged: boolean;
}

export interface DashboardKpis {
  total_hours: number;
  logged_days: number;
  weekdays: number;
  rate: number;
  avg: number;
  streak: number;
}

export interface DashboardCounts {
  open_stories: number;
  closed_stories: number;
  open_subtasks: number;
  closed_subtasks: number;
}

export interface DashboardResponse {
  days: DashboardDay[];
  kpis: DashboardKpis;
  start: string;
  counts: DashboardCounts;
}

export interface RunStep {
  label: string;
  status: "ok" | "error";
  msg: string;
}

export interface RunResult {
  status: "done" | "error";
  steps: RunStep[];
  finalStatus?: string | null;
  subtaskKey?: string;
  [key: string]: unknown;
}

export interface RequestItem {
  id: string;
  type: "epic" | "story" | "subtask" | "timelog";
  mode: "create" | "edit";
  target_key: string | null;
  context: Record<string, unknown>;
  fields: Record<string, unknown>;
  diff: Record<string, unknown>;
  status: "pending" | "done" | "error";
  result: string | null;
}

export interface WorklogEntry {
  date: string;
  story_key: string;
  work_type: string;
  subtask_title: string;
  subtask_description: string;
  acceptance: string;
  repo: string;
  branch: string;
  commit: string;
  tasks: string[];
}

export interface WorklogFile {
  name: string;
  path: string;
}

export interface AssignableUser {
  accountId: string;
  displayName: string;
}

export interface Priority {
  id: string;
  name: string;
}
