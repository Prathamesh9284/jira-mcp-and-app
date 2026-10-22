"use client";

import { Fragment, useEffect, useState } from "react";
import { api, DashboardResponse, DashboardDay } from "@/lib/api";

const WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri"];

function ActivityHeatmap({ days }: { days: DashboardDay[] }) {
  if (days.length === 0) return <p className="text-muted text-sm">No weekdays in range.</p>;

  const weekStarts = Array.from(new Set(days.map((d) => d.week_start))).sort();
  const cellByKey = new Map(days.map((d) => [`${d.week_start}|${d.weekday_name}`, d]));
  // Fixed label column, cells stretch evenly to fill the rest of the card's width.
  const cols = `3.5rem repeat(${weekStarts.length}, minmax(28px, 1fr))`;

  return (
    <div className="w-full">
      <div className="grid gap-2 mb-1" style={{ gridTemplateColumns: cols }}>
        <div />
        {weekStarts.map((ws) => (
          <div key={ws} className="text-xs text-muted text-center truncate">
            {ws.slice(5)}
          </div>
        ))}
      </div>
      <div className="grid gap-2" style={{ gridTemplateColumns: cols }}>
        {WEEKDAY_NAMES.map((wd) => (
          <Fragment key={wd}>
            <div className="text-sm text-muted pr-2 flex items-center h-10">{wd}</div>
            {weekStarts.map((ws) => {
              const cell = cellByKey.get(`${ws}|${wd}`);
              return (
                <div
                  key={`${ws}-${wd}`}
                  title={cell ? `${cell.date} — ${cell.hours}h` : ws}
                  className={`h-10 w-full rounded-md ${
                    cell?.logged ? "bg-green-600" : "bg-red-900/70"
                  }`}
                />
              );
            })}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<DashboardResponse>("/dashboard?weeks=12")
      .then(setData)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="text-red-300">Failed to load dashboard: {error}</p>;
  if (!data) return <p className="text-muted">Loading…</p>;

  const { kpis, counts, days, start } = data;

  return (
    <div className="flex flex-col gap-8">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <KpiTile label="Total hours" value={kpis.total_hours} />
        <KpiTile label="Logged days" value={`${kpis.logged_days}/${kpis.weekdays}`} />
        <KpiTile label="Logging rate" value={`${kpis.rate}%`} />
        <KpiTile label="Avg hrs/day" value={kpis.avg} />
        <KpiTile label="Streak" value={`${kpis.streak}d`} />
        <KpiTile label="Since" value={start} />
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <CountTile label="Open stories" value={counts.open_stories} />
        <CountTile label="Closed stories" value={counts.closed_stories} />
        <CountTile label="Open sub-tasks" value={counts.open_subtasks} />
        <CountTile label="Closed sub-tasks" value={counts.closed_subtasks} />
      </div>

      <div className="rounded-2xl border border-line bg-surface p-5">
        <h2 className="text-ink font-semibold mb-1">Activity</h2>
        <p className="text-muted text-xs mb-4">🟩 logged · 🟥 not logged · weekends skipped</p>
        <ActivityHeatmap days={days} />
      </div>
    </div>
  );
}

function KpiTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <p className="text-muted text-xs">{label}</p>
      <p className="text-ink text-xl font-bold mt-1">{value}</p>
    </div>
  );
}

function CountTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-line bg-surface2 p-4">
      <p className="text-muted text-xs">{label}</p>
      <p className="text-ink text-xl font-bold mt-1">{value}</p>
    </div>
  );
}
