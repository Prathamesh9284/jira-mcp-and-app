"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

export interface GanttRow {
  key: string;
  summary: string;
  status: string;
  start_date: string | null;
  due_date: string | null;
}

interface WorklogIssue {
  key: string;
  summary: string;
  days: Record<string, number>;
}

const DAY_MS = 86400000;

function isoDay(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function dayRange(fromIso: string, toIso: string): string[] {
  const out: string[] = [];
  for (let t = new Date(fromIso + "T00:00:00Z").getTime();
       t <= new Date(toIso + "T00:00:00Z").getTime(); t += DAY_MS) {
    out.push(new Date(t).toISOString().slice(0, 10));
  }
  return out;
}

// Sequential ramp for hours-logged magnitude (one hue, monotone lightness — validated
// against the dark surface with the dataviz palette validator; anchored so more hours
// reads brighter on dark).
function hoursColor(seconds: number): string {
  const h = seconds / 3600;
  if (h <= 0) return "";
  if (h <= 2) return "#2d5580";
  if (h <= 4) return "#3a70ae";
  if (h <= 6) return "#4488dd";
  return "#4c9aff";
}

function fmtHours(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return m ? `${h}h ${m}m` : `${h}h`;
}

function DayHeader({ days }: { days: string[] }) {
  return (
    <>
      <div />
      {days.map((d) => {
        const dt = new Date(d + "T00:00:00Z");
        const weekend = dt.getUTCDay() === 0 || dt.getUTCDay() === 6;
        return (
          <div key={d} className={`text-center text-[10px] ${weekend ? "text-muted/50" : "text-muted"}`}>
            {d.slice(8)}
            <span className="block">{d.slice(5, 7)}</span>
          </div>
        );
      })}
    </>
  );
}

function ScheduleGantt({ rows }: { rows: GanttRow[] }) {
  const dated = rows.filter((r) => r.start_date && r.due_date);
  const undated = rows.filter((r) => !r.start_date || !r.due_date);

  const days = useMemo(() => {
    if (dated.length === 0) return [];
    let min = dated[0].start_date!, max = dated[0].due_date!;
    for (const r of dated) {
      if (r.start_date! < min) min = r.start_date!;
      if (r.due_date! > max) max = r.due_date!;
    }
    return dayRange(min, max).slice(0, 60);
  }, [dated]);

  if (dated.length === 0) {
    return <p className="text-xs text-muted">No start/due dates on the current items — nothing to plot.</p>;
  }

  const today = isoDay(new Date());
  const grid = { gridTemplateColumns: `220px repeat(${days.length}, minmax(22px, 1fr))` };

  return (
    <div className="overflow-x-auto">
      <div className="grid gap-[2px] items-center" style={grid}>
        <DayHeader days={days} />
        {dated.map((r) => {
          const from = Math.max(0, days.indexOf(r.start_date!));
          const to = days.indexOf(r.due_date!) === -1 ? days.length - 1 : days.indexOf(r.due_date!);
          return (
            <Fragment key={r.key}>
              <div className="truncate pr-2 text-xs text-ink">
                <span className="font-medium text-brand">{r.key}</span>
                <span className="text-muted"> {r.summary.slice(0, 28)}</span>
              </div>
              {days.map((d, i) => (
                <div key={`${r.key}-${d}`} className={`h-5 ${d === today ? "bg-surface2/60" : ""}`}>
                  {i >= from && i <= to && (
                    <div
                      title={`${r.key} · ${r.start_date} → ${r.due_date}`}
                      className={`h-4 mt-0.5 bg-brand/90 ${i === from ? "rounded-l" : ""} ${i === to ? "rounded-r" : ""}`}
                    />
                  )}
                </div>
              ))}
            </Fragment>
          );
        })}
      </div>
      {undated.length > 0 && (
        <p className="mt-2 text-[11px] text-muted">
          No dates: {undated.map((r) => r.key).join(", ")}
        </p>
      )}
    </div>
  );
}

function WorklogGantt({ refresh }: { refresh: number }) {
  const [issues, setIssues] = useState<WorklogIssue[]>([]);
  const [since, setSince] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    // Always all of the user's logged time — not scoped to whatever epic/story is picked
    // in the drill-down table above, that picker is for Schedule, not Timelog.
    api
      .get<{ since: string; issues: WorklogIssue[] }>("/timelog/gantt?days=14")
      .then((r) => {
        setSince(r.since);
        setIssues(r.issues);
      })
      .catch(() => setIssues([]))
      .finally(() => setLoading(false));
  }, [refresh]);

  if (loading) return <p className="text-xs text-muted">Loading worklogs…</p>;
  if (issues.length === 0) return <p className="text-xs text-muted">No time logged in the last 14 days.</p>;

  const days = dayRange(since, isoDay(new Date()));
  const today = isoDay(new Date());
  const grid = { gridTemplateColumns: `220px repeat(${days.length}, minmax(24px, 1fr))` };

  return (
    <div className="overflow-x-auto">
      <div className="grid gap-[2px] items-center" style={grid}>
        <DayHeader days={days} />
        {issues.map((iss) => (
          <Fragment key={iss.key}>
            <div className="truncate pr-2 text-xs text-ink">
              <span className="font-medium text-brand">{iss.key}</span>
              <span className="text-muted"> {iss.summary.slice(0, 28)}</span>
            </div>
            {days.map((d) => {
              const secs = iss.days[d] || 0;
              const bg = hoursColor(secs);
              return (
                <div
                  key={`${iss.key}-${d}`}
                  title={secs ? `${iss.key} · ${d} · ${fmtHours(secs)}` : undefined}
                  className={`h-5 rounded-[3px] ${!bg ? (d === today ? "bg-surface2/60" : "bg-surface2/30") : ""}`}
                  style={bg ? { backgroundColor: bg } : undefined}
                />
              );
            })}
          </Fragment>
        ))}
      </div>
      <div className="mt-2 flex items-center gap-2 text-[11px] text-muted">
        Hours:
        {[["≤2", "#2d5580"], ["≤4", "#3a70ae"], ["≤6", "#4488dd"], ["6+", "#4c9aff"]].map(([label, c]) => (
          <span key={label} className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-[3px]" style={{ backgroundColor: c }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Schedule vs Timelog gantt, tab-toggled. Schedule plots the drill-down table's current
 * rows by start→due date; Timelog plots the user's actual logged hours per issue per day. */
export default function GanttTabs({ rows, ganttRefresh = 0 }: { rows: GanttRow[]; ganttRefresh?: number }) {
  const [tab, setTab] = useState<"schedule" | "timelog">("timelog");
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4">
      <div className="flex gap-2">
        {(["schedule", "timelog"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
              tab === t ? "bg-surface2 text-ink border border-line" : "text-muted hover:bg-surface2/60"
            }`}
          >
            {t === "schedule" ? "Schedule" : "Timelog"}
          </button>
        ))}
      </div>
      {tab === "schedule" ? <ScheduleGantt rows={rows} /> : <WorklogGantt refresh={ganttRefresh} />}
    </div>
  );
}
