"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { applySse, createRun } from "./run-model";
import { readSse } from "./sse";
import type { RunModel } from "./types";

/**
 * Drives one planner run over the existing SSE endpoints (`/runs`, `/runs/{id}/resume`).
 * No new backend contract: the request is the same text string the dashboard sends.
 */
export function useTripRun() {
  const [model, setModel] = useState<RunModel>(createRun());
  const threadRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(async (request: string, resume?: string) => {
    const threadId = threadRef.current;
    if (resume && !threadId) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    if (!resume) {
      threadRef.current = null;
      setModel({ ...createRun(), status: "running" });
    } else {
      setModel((current) => ({ ...current, status: "running", question: null, error: null }));
    }
    const path = resume ? `/api/planner/runs/${threadId}/resume` : "/api/planner/runs";
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { "content-type": "application/json", accept: "text/event-stream" },
        body: JSON.stringify({ request, resume: resume ?? null }),
        signal: controller.signal,
      });
      if (!response.ok) {
        const detail = await response.text();
        setModel((current) => ({
          ...current,
          status: "error",
          error: friendly(detail) || "The planner could not start. Please try again.",
        }));
        return;
      }
      await readSse(response, (event, data) => {
        setModel((current) => {
          const next = applySse(current, event, data);
          threadRef.current = next.threadId;
          return next;
        });
      });
      // A stream that ends without done/interrupt/error means the connection dropped.
      setModel((current) =>
        current.status === "running"
          ? { ...current, status: "error", error: "The connection to the planner was interrupted." }
          : current,
      );
    } catch (error) {
      if ((error as Error).name === "AbortError") return;
      setModel((current) => ({
        ...current,
        status: "error",
        error: "We couldn\u2019t reach the planner service. Check that it is running and try again.",
      }));
    }
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setModel((current) => ({ ...current, status: "idle", running: [] }));
  }, []);

  useEffect(() => () => abortRef.current?.abort(), []);

  return { model, start, cancel };
}

function friendly(detail: string): string {
  try {
    const parsed = JSON.parse(detail) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
  } catch {
    /* plain text */
  }
  return detail.length > 240 ? "" : detail;
}
