import type {
  AgentEvent,
  LlmMeta,
  PlanSlice,
  RevisionFrame,
  RunModel,
  Snapshot,
  Violation,
} from "./types";

let rowSeq = 0;

export function createRun(): RunModel {
  return {
    threadId: null,
    status: "idle",
    error: null,
    question: null,
    liveApis: false,
    apiCallBudget: 40,
    durableResume: false,
    llm: null,
    rows: [],
    running: [],
    finishedNodes: [],
    snapshot: null,
    revisions: [],
    pendingBefore: null,
    awaitingAfter: false,
    revisionSummary: "",
  };
}

export function applySse(model: RunModel, event: string, data: unknown): RunModel {
  const next = clone(model);
  if (event === "meta" && isRecord(data)) {
    next.threadId = typeof data.thread_id === "string" ? data.thread_id : next.threadId;
    next.liveApis = Boolean(data.live_apis);
    next.apiCallBudget = typeof data.api_call_budget === "number" ? data.api_call_budget : 40;
    next.durableResume = Boolean(data.durable_resume);
    next.llm = isRecord(data.llm) ? (data.llm as LlmMeta) : next.llm;
    if (next.status === "idle") next.status = "running";
    return next;
  }
  if (event === "state" && isRecord(data) && isRecord(data.snapshot)) {
    const snapshot = data.snapshot as Snapshot;
    next.snapshot = snapshot;
    return closeRevision(next, typeof data.node === "string" ? data.node : "", snapshot);
  }
  if (event === "interrupt" && isRecord(data)) {
    next.status = "needs_input";
    next.running = [];
    const pending = Array.isArray(data.interrupts) ? data.interrupts : [];
    const first = pending.find(isRecord);
    next.question =
      first && typeof first.question === "string"
        ? first.question
        : "How many days should the trip be (1-7)?";
    return next;
  }
  if (event === "done") {
    next.status = "done";
    next.running = [];
    return next;
  }
  if (event === "error" && isRecord(data)) {
    next.status = "error";
    next.running = [];
    next.error = typeof data.detail === "string" ? data.detail : "The planner run failed.";
    return next;
  }
  if (event === "message" && isAgentEvent(data)) {
    return applyAgent(next, data);
  }
  return next;
}

export function planSlice(snapshot: Snapshot): PlanSlice {
  const days = snapshot.draft?.days ?? snapshot.final?.days ?? [];
  const budget = snapshot.budget ?? snapshot.draft?.budget ?? snapshot.final?.budget ?? null;
  const stay = snapshot.draft?.stay ?? snapshot.final?.stay ?? null;
  return {
    total: budget ? budget.total_aed : null,
    within: budget ? budget.within_budget : null,
    themes: days.map((day) => day.theme),
    stay: stay?.name ?? null,
    violations: snapshot.review?.violations ?? [],
    holidayNotes: snapshot.holiday_notes ?? [],
  };
}

function applyAgent(model: RunModel, event: AgentEvent): RunModel {
  if (model.status === "idle" || model.status === "needs_input") model.status = "running";
  if (event.phase === "start") {
    model.rows.push({
      id: `row-${rowSeq++}`,
      node: event.node,
      status: "running",
      summary: event.summary,
      durationMs: null,
      delta: event.state_delta ?? {},
    });
    model.running = [...model.running.filter((name) => name !== event.node), event.node];
    return model;
  }
  if (event.phase === "revision") {
    model.rows.push({
      id: `row-${rowSeq++}`,
      node: event.node,
      status: "revision",
      summary: event.summary,
      durationMs: event.duration_ms ?? null,
      delta: event.state_delta ?? {},
    });
    model.awaitingAfter = true;
    model.revisionSummary = event.summary;
    return model;
  }
  const open = [...model.rows].reverse().find((row) => row.node === event.node && row.status === "running");
  if (open) {
    open.status = event.phase === "error" ? "error" : "done";
    open.summary = event.summary;
    open.durationMs = event.duration_ms ?? null;
    open.delta = event.state_delta ?? {};
  } else {
    model.rows.push({
      id: `row-${rowSeq++}`,
      node: event.node,
      status: event.phase === "error" ? "error" : "done",
      summary: event.summary,
      durationMs: event.duration_ms ?? null,
      delta: event.state_delta ?? {},
    });
  }
  model.running = model.running.filter((name) => name !== event.node);
  if (event.phase === "end") model.finishedNodes.push(event.node);
  if (event.phase === "error") {
    model.status = "error";
    model.error = event.summary;
  }
  return model;
}

function closeRevision(model: RunModel, node: string, snapshot: Snapshot): RunModel {
  const slice = planSlice(snapshot);
  const closes = node === "budget" || node === "review";
  if (model.awaitingAfter && closes && model.pendingBefore) {
    const frame: RevisionFrame = {
      id: `rev-${model.revisions.length + 1}`,
      summary: model.revisionSummary,
      before: model.pendingBefore,
      after: slice,
      violations: model.pendingBefore.violations,
    };
    model.revisions = [...model.revisions, frame];
    model.awaitingAfter = false;
    model.revisionSummary = "";
  }
  if (node === "review" && snapshot.review && !snapshot.review.passed) {
    model.pendingBefore = slice;
  } else if (node === "review" && snapshot.review?.passed) {
    model.pendingBefore = null;
  }
  return model;
}

function clone(model: RunModel): RunModel {
  return {
    ...model,
    rows: model.rows.map((row) => ({ ...row, delta: { ...row.delta } })),
    running: [...model.running],
    finishedNodes: [...model.finishedNodes],
    revisions: model.revisions.map((frame) => ({ ...frame, violations: [...frame.violations] })),
    llm: model.llm ? { ...model.llm } : null,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isAgentEvent(value: unknown): value is AgentEvent {
  if (!isRecord(value)) return false;
  return typeof value.node === "string" && typeof value.phase === "string" && typeof value.summary === "string";
}

export function violationLines(violations: Violation[]): string[] {
  return violations.map((row) => `${row.severity} ${row.rule}: ${row.detail}`);
}
