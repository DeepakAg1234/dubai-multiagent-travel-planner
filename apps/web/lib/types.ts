export type AgentEvent = {
  ts: string;
  node: string;
  phase: "start" | "end" | "error" | "revision";
  summary: string;
  state_delta: Record<string, unknown>;
  duration_ms?: number | null;
  tokens?: Record<string, number> | null;
};

export type LlmMeta = {
  default_provider: string;
  default_model: string;
  default_enabled: boolean;
  review_provider: string;
  review_model: string;
  review_enabled: boolean;
};

export type UsageRow = {
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  repairs: number;
  fallbacks: number;
};

export type Label = {
  name: string;
  area: string;
  lat: number;
  lng: number;
  kind: string;
  category?: string | null;
  operational_status?: string | null;
};

export type Slot = {
  start: string;
  end: string;
  place_id?: string | null;
  kind: string;
  notes?: string | null;
};

export type Leg = {
  from_id: string;
  to_id: string;
  mode: string;
  minutes: number;
  distance_km: number;
  cost_aed?: number | null;
  provenance: string;
  source?: string;
};

export type DayPlan = {
  day: number;
  theme: string;
  slots: Slot[];
  legs: Leg[];
  holiday_note?: string | null;
};

export type BudgetLine = {
  category: string;
  item: string;
  unit_aed: number;
  quantity: number;
  total_aed: number;
  provenance: string;
};

export type BudgetReport = {
  lines: BudgetLine[];
  by_category: Record<string, number>;
  total_aed: number;
  budget_aed?: number | null;
  variance_aed?: number | null;
  within_budget: boolean;
  alternatives?: { kind: string; description: string; savings_aed: number; new_total_aed: number }[];
};

export type Violation = {
  rule: string;
  severity: "blocker" | "warning";
  detail: string;
  route_to: string;
};

export type ReviewReport = {
  passed: boolean;
  violations: Violation[];
};

export type Itinerary = {
  days: DayPlan[];
  stay?: {
    id?: string;
    name?: string;
    area?: string;
    tier?: string;
    season?: string;
    nightly_min_aed?: number;
    nightly_max_aed?: number;
    metro_nearby?: string | null;
    provenance?: string;
  } | null;
  budget?: BudgetReport | null;
  assumptions?: string[];
  warnings?: string[];
  revision_history?: string[];
  narrative?: string;
};

export type Snapshot = {
  constraints: Record<string, unknown> | null;
  assumptions: string[];
  plan_brief: { days?: { day: number; theme: string; areas?: string[] }[] } | null;
  candidates: {
    places: { id: string; name: string; area: string; operational_status?: string }[];
    restaurants: { id: string; name: string; area: string; price_band: string }[];
    areas: string[];
  } | null;
  draft: Itinerary | null;
  budget: BudgetReport | null;
  review: ReviewReport | null;
  revision_count: number;
  excluded_ids: string[];
  warnings: string[];
  holiday_notes: string[];
  final: Itinerary | null;
  labels: Record<string, Label>;
  degraded: boolean;
  attributions: string[];
  usage: Record<string, UsageRow>;
};

export type PlanSlice = {
  total: number | null;
  within: boolean | null;
  themes: string[];
  stay: string | null;
  violations: Violation[];
  holidayNotes: string[];
};

export type RevisionFrame = {
  id: string;
  summary: string;
  before: PlanSlice;
  after: PlanSlice;
  violations: Violation[];
};

export type TimelineRow = {
  id: string;
  node: string;
  status: "running" | "done" | "error" | "revision";
  summary: string;
  durationMs: number | null;
  delta: Record<string, unknown>;
};

export type RunStatus = "idle" | "running" | "needs_input" | "done" | "error";

export type RunModel = {
  threadId: string | null;
  status: RunStatus;
  error: string | null;
  question: string | null;
  liveApis: boolean;
  apiCallBudget: number;
  durableResume: boolean;
  llm: LlmMeta | null;
  rows: TimelineRow[];
  running: string[];
  finishedNodes: string[];
  snapshot: Snapshot | null;
  revisions: RevisionFrame[];
  pendingBefore: PlanSlice | null;
  awaitingAfter: boolean;
  revisionSummary: string;
};
