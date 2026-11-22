"use client";

import { useEffect, useRef, useState } from "react";

import { GraphView } from "@/components/GraphView";
import { InputPanel } from "@/components/InputPanel";
import { Results, type ResultTab } from "@/components/Results";
import { RevisionDiff } from "@/components/RevisionDiff";
import { StateInspector } from "@/components/StateInspector";
import { Timeline } from "@/components/Timeline";
import { UsagePanel } from "@/components/UsagePanel";
import { composeRequest, EMPTY_OVERRIDES, type Overrides } from "@/lib/compose";
import { applySse, createRun } from "@/lib/run-model";
import { readSse } from "@/lib/sse";
import type { RunModel } from "@/lib/types";

const WORKSPACE = ["graph", "state", "revisions", "itinerary", "budget", "notes", "map"] as const;
type WorkspaceTab = (typeof WORKSPACE)[number];

export function PlannerApp() {
  const [text, setText] = useState("");
  const [overrides, setOverrides] = useState<Overrides>(EMPTY_OVERRIDES);
  const [live, setLive] = useState(false);
  const [model, setModel] = useState<RunModel>(createRun());
  const [diagram, setDiagram] = useState("");
  const [tab, setTab] = useState<WorkspaceTab>("itinerary");
  const [answer, setAnswer] = useState("");
  const threadRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch("/api/planner/graph");
        if (!response.ok) return;
        const body = (await response.json()) as { mermaid?: string };
        if (!cancelled) setDiagram(body.mermaid ?? "");
      } catch {
        if (!cancelled) setDiagram("");
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function run(resume?: string) {
    const threadId = threadRef.current;
    if (resume && !threadId) return;
    if (!resume) {
      threadRef.current = null;
      setModel({ ...createRun(), status: "running" });
    } else {
      setModel((current) => ({ ...current, status: "running", question: null, error: null }));
    }
    const path = resume ? `/api/planner/runs/${threadId}/resume` : "/api/planner/runs";
    const response = await fetch(path, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "text/event-stream" },
      body: JSON.stringify({
        request: composeRequest(text, overrides),
        use_live_apis: live,
        resume: resume ?? null,
      }),
    });
    if (!response.ok) {
      const detail = await response.text();
      setModel((current) => ({ ...current, status: "error", error: detail || "The planner API rejected the run." }));
      return;
    }
    await readSse(response, (event, data) => {
      setModel((current) => {
        const next = applySse(current, event, data);
        threadRef.current = next.threadId;
        return next;
      });
    });
  }

  const busy = model.status === "running";
  const planReady = Boolean(model.snapshot?.final ?? model.snapshot?.draft);
  const resultTab: ResultTab | null =
    tab === "itinerary" || tab === "budget" || tab === "notes" || tab === "map" ? tab : null;

  return (
    <>
    <header className="topnav">
      <div className="topnav-inner">
        <span className="brand">
          <span className="brand-mark" aria-hidden="true">✈</span>
          dubaiplanner
        </span>
        {model.threadId && planReady ? (
          <div className="downloads">
            <a href={`/api/planner/runs/${model.threadId}/result?download=1`}>
              <span className="hide-sm">Download&nbsp;</span>JSON
            </a>
            <a href={`/api/planner/runs/${model.threadId}/export.md`}>
              <span className="hide-sm">Download&nbsp;</span>Markdown
            </a>
          </div>
        ) : null}
      </div>
    </header>
    <div className="app">
      <section className="hero">
        <p className="eyebrow">Dubai</p>
        <h1>Plan your next getaway</h1>
        <p className="lede">
          Watch each agent, the graph, and the budget as a run streams. Downloads are built when you ask for them.
        </p>
      </section>
      {model.status === "needs_input" ? (
        <form
          className="banner"
          onSubmit={(event) => {
            event.preventDefault();
            if (answer.trim()) void run(answer.trim());
          }}
        >
          <p>{model.question}</p>
          <p className="note">
            {model.durableResume
              ? "This answer resumes the saved checkpoint."
              : "This answer resumes the run in this server process only."}
          </p>
          <label>
            Answer
            <input value={answer} onChange={(event) => setAnswer(event.target.value)} />
          </label>
          <button className="primary" type="submit" disabled={busy || !answer.trim()}>
            Continue
          </button>
        </form>
      ) : null}
      {model.error ? <p className="banner">{model.error}</p> : null}
      <div className="workspace">
        <div className="stack">
          <InputPanel
            text={text}
            overrides={overrides}
            live={live}
            busy={busy}
            onText={setText}
            onOverrides={setOverrides}
            onLive={setLive}
            onSubmit={() => void run()}
          />
          <Timeline rows={model.rows} />
          <UsagePanel
            llm={model.llm}
            usage={model.snapshot?.usage ?? {}}
            budget={model.apiCallBudget}
            degraded={Boolean(model.snapshot?.degraded)}
            attributions={model.snapshot?.attributions ?? []}
          />
        </div>
        <section className="card">
          <div className="tabs" role="tablist" aria-label="Planner views">
            {WORKSPACE.map((name) => (
              <button
                key={name}
                type="button"
                role="tab"
                aria-selected={tab === name}
                onClick={() => setTab(name)}
              >
                {name}
              </button>
            ))}
          </div>
          {tab === "graph" ? (
            <GraphView diagram={diagram} running={model.running} finished={model.finishedNodes} />
          ) : null}
          {tab === "state" ? <StateInspector snapshot={model.snapshot} /> : null}
          {tab === "revisions" ? <RevisionDiff frames={model.revisions} /> : null}
          {resultTab ? <Results snapshot={model.snapshot} tab={resultTab} /> : null}
        </section>
      </div>
    </div>
    </>
  );
}
