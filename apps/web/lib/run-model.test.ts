import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { composeRequest, EMPTY_OVERRIDES } from "./compose.ts";
import { styleGraph } from "./graph-style.ts";
import { applySse, createRun } from "./run-model.ts";
import type { Snapshot } from "./types.ts";

describe("composeRequest", () => {
  it("appends structured overrides under the free-text request", () => {
    const text = composeRequest("culture and beaches", {
      ...EMPTY_OVERRIDES,
      days: "4",
      budget: "5000",
      startDate: "2026-11-18",
      hotelTier: "budget",
      avoidCrowds: true,
      interests: "culture food",
    });
    assert.match(text, /days: 4/);
    assert.match(text, /AED 5000/);
    assert.match(text, /2026-11-18/);
    assert.match(text, /budget hotel/);
    assert.match(text, /avoid crowds/);
    assert.match(text, /culture food/);
  });
});

describe("styleGraph", () => {
  it("highlights the running node and marks finished nodes", () => {
    const styled = styleGraph("graph TD;\n  parse_request(parse_request)", ["budget"], ["parse_request"]);
    assert.match(styled, /style parse_request fill:#f2f2f2/);
    assert.match(styled, /style budget fill:#ffe1e7/);
  });

  it("ignores ids that are not graph node names", () => {
    const styled = styleGraph("graph TD;", ["budget); classDef x"], []);
    assert.equal(styled, "graph TD;");
  });
});

describe("applySse", () => {
  it("records a revision diff from the review and the following budget", () => {
    let model = createRun();
    model = applySse(model, "meta", {
      thread_id: "thread-1",
      live_apis: false,
      api_call_budget: 40,
      durable_resume: false,
      llm: {
        default_provider: "ollama",
        default_model: "nemotron-3-nano",
        default_enabled: false,
        review_provider: "groq",
        review_model: "openai/gpt-oss-20b",
        review_enabled: false,
      },
    });
    model = applySse(model, "message", event("review", "end", "2 blocker(s)."));
    model = applySse(model, "state", { node: "review", snapshot: snap(3000, false) });
    model = applySse(model, "message", event("budget_adjust", "revision", "Revision 1: cheaper hotel"));
    model = applySse(model, "state", { node: "budget", snapshot: snap(2100, false) });
    assert.equal(model.threadId, "thread-1");
    assert.equal(model.revisions.length, 1);
    assert.equal(model.revisions[0]?.before.total, 3000);
    assert.equal(model.revisions[0]?.after.total, 2100);
    assert.equal(model.revisions[0]?.violations[0]?.rule, "budget_compliance");
    assert.equal(model.rows.some((row) => row.status === "revision"), true);
  });

  it("asks for the missing trip length", () => {
    const model = applySse(createRun(), "interrupt", {
      thread_id: "ask",
      interrupts: [{ missing: ["days"], question: "How many days should the trip be (1-7)?" }],
    });
    assert.equal(model.status, "needs_input");
    assert.match(model.question ?? "", /How many days/);
  });
});

function event(node: string, phase: string, summary: string) {
  return {
    ts: "2026-11-18T00:00:00Z",
    node,
    phase,
    summary,
    state_delta: {},
    duration_ms: 4,
  };
}

function snap(total: number, passed: boolean): Snapshot {
  return {
    constraints: { days: 2, budget_aed: 2200 },
    assumptions: [],
    plan_brief: null,
    candidates: null,
    draft: {
      days: [{ day: 1, theme: "Old Dubai", slots: [], legs: [] }],
      stay: { name: "Creek Hotel" },
      budget: {
        lines: [],
        by_category: { accommodation: total },
        total_aed: total,
        within_budget: total <= 2200,
      },
    },
    budget: {
      lines: [],
      by_category: { accommodation: total },
      total_aed: total,
      within_budget: total <= 2200,
    },
    review: {
      passed,
      violations: passed
        ? []
        : [
            {
              rule: "budget_compliance",
              severity: "blocker",
              detail: "over",
              route_to: "budget_adjust",
            },
          ],
    },
    revision_count: passed ? 1 : 0,
    excluded_ids: [],
    warnings: [],
    holiday_notes: [],
    final: null,
    labels: {},
    degraded: false,
    attributions: [],
    usage: {},
  };
}
