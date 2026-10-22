"use client";

import { useEffect, useState } from "react";
import { api, HealthResponse } from "@/lib/api";

export default function HealthBanner() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<HealthResponse>("/health")
      .then(setHealth)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <div className="bg-red-950/60 border-b border-red-800 text-red-200 text-sm px-4 py-2">
        Could not reach backend: {error}
      </div>
    );
  }
  if (!health || (health.jira && health.llm)) return null;

  return (
    <div className="bg-yellow-950/60 border-b border-yellow-800 text-yellow-200 text-sm px-4 py-2">
      {!health.jira && "Jira not configured. "}
      {!health.llm && "LLM not configured. "}
      Missing: {health.missing.join(", ") || "—"}
    </div>
  );
}
