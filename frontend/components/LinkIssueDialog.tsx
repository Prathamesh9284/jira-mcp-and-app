"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useToast } from "@/components/Toast";

const inputCls =
  "w-full rounded-lg border border-line bg-surface2 px-3 py-2 text-sm text-ink outline-none focus:border-brand";

interface LinkType {
  id: string;
  name: string;
  inward: string;
  outward: string;
}

// One selectable row in the dropdown — each link type expands into two directions.
interface LinkOption {
  typeName: string;
  label: string;       // e.g. "blocks" or "is blocked by"
  thisIsOutward: boolean; // true → thisKey=outward, otherKey=inward
}

interface Props {
  defaultKey?: string;   // pre-fill "this issue"
  onClose: () => void;
  onLinked?: (inward: string, outward: string, type: string) => void;
}

export default function LinkIssueDialog({ defaultKey = "", onClose, onLinked }: Props) {
  const [options, setOptions] = useState<LinkOption[]>([]);
  const [optionIdx, setOptionIdx] = useState(0);
  const [thisKey, setThisKey] = useState(defaultKey);
  const [otherKey, setOtherKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const overlayRef = useRef<HTMLDivElement>(null);
  const toast = useToast();

  useEffect(() => {
    api.get<LinkType[]>("/link-types").then((types) => {
      const opts: LinkOption[] = [];
      for (const t of types) {
        opts.push({ typeName: t.name, label: t.outward, thisIsOutward: true });
        opts.push({ typeName: t.name, label: t.inward,  thisIsOutward: false });
      }
      setOptions(opts);
      // Default to "relates to" / first option
      const defaultIdx = opts.findIndex((o) => o.label.toLowerCase().includes("relat"));
      setOptionIdx(defaultIdx >= 0 ? defaultIdx : 0);
    }).catch(() => {
      // Fallback so the dialog is still usable
      setOptions([
        { typeName: "Relates",  label: "relates to",    thisIsOutward: true  },
        { typeName: "Blocks",   label: "blocks",         thisIsOutward: true  },
        { typeName: "Blocks",   label: "is blocked by",  thisIsOutward: false },
        { typeName: "Cloners",  label: "clones",         thisIsOutward: true  },
        { typeName: "Cloners",  label: "is cloned by",   thisIsOutward: false },
        { typeName: "Duplicate","label": "duplicates",   thisIsOutward: true  } as LinkOption,
        { typeName: "Duplicate","label": "is duplicated by", thisIsOutward: false } as LinkOption,
      ]);
    });
  }, []);

  const selected = options[optionIdx];

  const submit = async () => {
    if (!thisKey.trim() || !otherKey.trim() || !selected) return;
    setSubmitting(true);
    const inwardKey  = selected.thisIsOutward ? otherKey.trim() : thisKey.trim();
    const outwardKey = selected.thisIsOutward ? thisKey.trim()  : otherKey.trim();
    try {
      await api.post("/issues/link", {
        inwardKey,
        outwardKey,
        linkType: selected.typeName,
      });
      toast("success", `${thisKey.trim()} ${selected.label} ${otherKey.trim()}`);
      onLinked?.(inwardKey, outwardKey, selected.typeName);
      onClose();
    } catch (e) {
      toast("error", e instanceof ApiError ? String(e.detail ?? e) : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
    >
      <div className="w-full max-w-md rounded-xl border border-line bg-surface p-6 shadow-xl flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-ink">Link Work Items</h2>
          <button onClick={onClose} className="text-muted hover:text-ink text-lg leading-none">✕</button>
        </div>

        <label className="flex flex-col gap-1 text-sm text-muted">
          This issue
          <input
            value={thisKey}
            onChange={(e) => setThisKey(e.target.value)}
            placeholder="WAR-123"
            className={inputCls}
            autoFocus={!defaultKey}
          />
        </label>

        <label className="flex flex-col gap-1 text-sm text-muted">
          Link type
          <select
            value={optionIdx}
            onChange={(e) => setOptionIdx(Number(e.target.value))}
            className={inputCls}
          >
            {options.map((o, i) => (
              <option key={i} value={i}>{o.label}</option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm text-muted">
          Linked issue
          <input
            value={otherKey}
            onChange={(e) => setOtherKey(e.target.value)}
            placeholder="WAR-456"
            className={inputCls}
            autoFocus={!!defaultKey}
          />
        </label>

        {selected && thisKey && otherKey && (
          <p className="text-xs text-muted bg-surface2 rounded-lg px-3 py-2">
            <span className="text-ink font-medium">{thisKey}</span>
            {" "}<span className="text-brand">{selected.label}</span>{" "}
            <span className="text-ink font-medium">{otherKey}</span>
          </p>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onClose} className="rounded-lg border border-line px-4 py-2 text-sm text-muted hover:text-ink">
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={submitting || !thisKey.trim() || !otherKey.trim() || !selected}
            className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {submitting ? "Linking…" : "Link"}
          </button>
        </div>
      </div>
    </div>
  );
}
