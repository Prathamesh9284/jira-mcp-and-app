"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";
import { CheckCircle2, XCircle, X } from "lucide-react";

interface ToastItem {
  id: number;
  kind: "success" | "error";
  text: string;
}

const ToastContext = createContext<(kind: ToastItem["kind"], text: string) => void>(() => {});

/** useToast()("success", "Time logged on PTA-6598") — fire-and-forget notifications,
 * bottom-right, auto-dismiss. Replaces the old inline result/step blocks. */
export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const push = useCallback((kind: ToastItem["kind"], text: string) => {
    const id = nextId.current++;
    setToasts((t) => [...t, { id, kind, text }]);
    // Errors linger longer — they carry detail worth reading.
    setTimeout(() => dismiss(id), kind === "error" ? 8000 : 4000);
  }, [dismiss]);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="fixed top-6 left-6 z-50 flex flex-col gap-2 max-w-sm">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`flex items-start gap-2 rounded-xl border p-3 text-sm shadow-lg ${
              t.kind === "success"
                ? "border-emerald-700 bg-emerald-950/90 text-emerald-100"
                : "border-red-800 bg-red-950/90 text-red-100"
            }`}
          >
            {t.kind === "success" ? (
              <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-400" />
            ) : (
              <XCircle size={16} className="mt-0.5 shrink-0 text-red-400" />
            )}
            <span className="whitespace-pre-wrap break-words">{t.text}</span>
            <button onClick={() => dismiss(t.id)} className="ml-auto shrink-0 opacity-60 hover:opacity-100">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
