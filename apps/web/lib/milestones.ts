import type { RunModel } from "./types";

/** Traveler-facing steps, each tied to the real graph nodes that perform it. */
export const MILESTONES = [
  { id: "understand", label: "Understanding your trip", nodes: ["parse_request", "ask_user"] },
  { id: "plan", label: "Organizing attractions into practical days", nodes: ["orchestrator_plan"] },
  { id: "discover", label: "Discovering experiences that match your interests", nodes: ["destination_research"] },
  { id: "routes", label: "Checking routes and travel logistics", nodes: ["logistics_prelim", "logistics_sequence"] },
  { id: "budget", label: "Balancing activities with your budget", nodes: ["budget", "budget_adjust"] },
  { id: "polish", label: "Preparing your personalized itinerary", nodes: ["review", "orchestrator_revise", "finalize"] },
] as const;

export type MilestoneState = "done" | "active" | "pending";

/** State comes only from events the backend actually emitted. */
export function milestoneStates(model: RunModel): { id: string; label: string; state: MilestoneState }[] {
  const started = new Set(model.rows.map((row) => row.node));
  const finished = new Set(model.finishedNodes);
  const running = new Set(model.running);
  const finalDone = model.status === "done";
  return MILESTONES.map((m) => {
    const nodes = m.nodes as readonly string[];
    const isRunning = nodes.some((n) => running.has(n));
    const touched = nodes.some((n) => started.has(n));
    const complete = nodes.some((n) => finished.has(n)) && !isRunning;
    let state: MilestoneState = "pending";
    if (finalDone || (complete && !isRunning && m.id !== "polish")) state = "done";
    if (isRunning) state = "active";
    else if (touched && state === "pending") state = "active";
    return { id: m.id, label: m.label, state };
  });
}
