"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError, IssueType, SubtaskType } from "@/lib/api";
import { useToast } from "@/components/Toast";

const inputCls =
  "w-full rounded-lg border border-line bg-surface2 px-3 py-2 text-sm text-ink outline-none focus:border-brand";
const compactCls =
  "w-full rounded-lg border border-line bg-surface2 px-2 py-1.5 text-sm text-ink outline-none focus:border-brand";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm text-muted">
      {label}
      {children}
    </label>
  );
}

interface WorklogRow {
  date: string;
  timeSpent: string;
  endTime: string;
}

interface Props {
  mode: "story" | "subtask";
  projectKey: string;
  epicKey?: string;
  storyKey?: string;
  onClose: () => void;
  onCreated: (key: string, summary: string, hasWorklogs: boolean) => void;
}

export default function CreateIssueDialog({ mode, projectKey, epicKey, storyKey, onClose, onCreated }: Props) {
  const [storyTypes, setStoryTypes] = useState<IssueType[]>([]);
  const [subtaskTypes, setSubtaskTypes] = useState<SubtaskType[]>([]);
  const [typeId, setTypeId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("-");
  const [acceptance, setAcceptance] = useState("-");
  const [parentKey, setParentKey] = useState(mode === "story" ? (epicKey ?? "") : (storyKey ?? ""));
  const [startDate, setStartDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [worklogs, setWorklogs] = useState<WorklogRow[]>([]);
  const [closeAfter, setCloseAfter] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);
  const toast = useToast();

  useEffect(() => {
    if (mode === "story") {
      api.get<IssueType[]>(`/story-types?project=${projectKey}`)
        .then((ts) => { setStoryTypes(ts); setTypeId(ts[0]?.id ?? ""); })
        .catch(() => setStoryTypes([]));
    } else {
      api.get<SubtaskType[]>(`/subtask-types?project=${projectKey}`)
        .then((ts) => { setSubtaskTypes(ts); setTypeId(ts[0]?.id ?? ""); })
        .catch(() => setSubtaskTypes([]));
    }
  }, [mode, projectKey]);

  const addWorklog = () => {
    setWorklogs((prev) => [
      ...prev,
      { date: new Date().toISOString().slice(0, 10), timeSpent: "", endTime: "" },
    ]);
  };

  const updateWorklog = (i: number, field: keyof WorklogRow, value: string) => {
    setWorklogs((prev) => prev.map((w, idx) => idx === i ? { ...w, [field]: value } : w));
  };

  const removeWorklog = (i: number) => {
    setWorklogs((prev) => prev.filter((_, idx) => idx !== i));
  };

  const submit = async () => {
    setSubmitting(true);
    try {
      if (mode === "story") {
        const r = await api.post<{ key: string }>("/story", {
          projectKey,
          issueTypeId: typeId,
          title,
          description,
          acceptance,
          epicKey: parentKey || null,
          startDate,
          endDate,
        });
        toast("success", `Created ${r.key}`);
        onCreated(r.key, title, false);
      } else {
        const r = await api.post<{ status: string; subtaskKey?: string }>("/subtask", {
          storyKey: parentKey,
          projectKey,
          issueTypeId: typeId || null,
          title,
          description,
          acceptance,
          startDate,
          endDate,
          worklogs,
          closeAfter,
        });
        const key = r.subtaskKey ?? "";
        toast("success", `Created ${key}${worklogs.length ? " · time logged" : ""}${closeAfter ? " · closed" : ""}`);
        onCreated(key, title, worklogs.length > 0);
      }
      onClose();
    } catch (e) {
      toast("error", e instanceof ApiError ? String(e.detail ?? e) : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = title.trim() && typeId && parentKey.trim();

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
    >
      <div className="w-full max-w-lg rounded-xl border border-line bg-surface p-6 shadow-xl flex flex-col gap-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-ink">
            {mode === "story" ? "Create Story / Task / Bug" : "Create Subtask"}
          </h2>
          <button onClick={onClose} className="text-muted hover:text-ink text-lg leading-none">✕</button>
        </div>

        <Field label={mode === "story" ? "Type" : "Work type"}>
          <select value={typeId} onChange={(e) => setTypeId(e.target.value)} className={inputCls}>
            {(mode === "story" ? storyTypes : subtaskTypes).map((t) => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
          </select>
        </Field>

        <Field label={mode === "story" ? "Epic key (optional)" : "Story key"}>
          <input
            value={parentKey}
            onChange={(e) => setParentKey(e.target.value)}
            placeholder={mode === "story" ? "WAR-123" : "WAR-456"}
            className={inputCls}
          />
        </Field>

        <Field label="Title">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Short summary"
            className={inputCls}
            autoFocus
          />
        </Field>

        <Field label="Description">
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} className={inputCls} rows={2} />
        </Field>

        <Field label="Acceptance criteria">
          <textarea value={acceptance} onChange={(e) => setAcceptance(e.target.value)} className={inputCls} rows={2} />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Start date">
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className={inputCls} />
          </Field>
          <Field label="Due date">
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className={inputCls} />
          </Field>
        </div>

        {mode === "subtask" && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted uppercase tracking-wide">Time Logs</span>
              <button
                type="button"
                onClick={addWorklog}
                className="text-xs text-brand hover:underline"
              >
                + Add time log
              </button>
            </div>

            {worklogs.length > 0 && (
              <div className="flex flex-col gap-2">
                <div className="grid grid-cols-[1fr_1fr_1fr_1.5rem] gap-1 text-xs text-muted px-1">
                  <span>Date</span><span>Time spent</span><span>End time</span><span />
                </div>
                {worklogs.map((wl, i) => (
                  <div key={i} className="grid grid-cols-[1fr_1fr_1fr_1.5rem] gap-1 items-center">
                    <input
                      type="date"
                      value={wl.date}
                      onChange={(e) => updateWorklog(i, "date", e.target.value)}
                      className={compactCls}
                    />
                    <input
                      value={wl.timeSpent}
                      onChange={(e) => updateWorklog(i, "timeSpent", e.target.value)}
                      placeholder="2h 30m"
                      className={compactCls}
                    />
                    <input
                      value={wl.endTime}
                      onChange={(e) => updateWorklog(i, "endTime", e.target.value)}
                      placeholder="17:00"
                      className={compactCls}
                    />
                    <button
                      type="button"
                      onClick={() => removeWorklog(i)}
                      className="text-muted hover:text-red-500 text-sm leading-none"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}

            {worklogs.length > 0 && (
              <label className="flex items-center gap-2 text-sm text-ink">
                <input
                  type="checkbox"
                  checked={closeAfter}
                  onChange={(e) => setCloseAfter(e.target.checked)}
                />
                Close subtask after logging
              </label>
            )}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onClose} className="rounded-lg border border-line px-4 py-2 text-sm text-muted hover:text-ink">
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={submitting || !canSubmit}
            className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {submitting ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}
