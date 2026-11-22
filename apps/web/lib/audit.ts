import type { Itinerary, Label } from "./types";

export type AuditFinding = {
  code: string;
  severity: "blocker" | "warning";
  title: string;
  detail: string;
};

export type RecognizedStop = {
  name: string;
  kind: string;
  area: string;
  day: number | null;
  status: string | null;
};

export type AuditReport = {
  verdict: "clear" | "repaired" | "still_blocked";
  headline: string;
  summary: string;
  assumptions: string[];
  repairs: string[];
  recognized: RecognizedStop[];
  unknown: string[];
  findings: AuditFinding[];
  remaining: AuditFinding[];
  original: Itinerary | null;
  repaired: Itinerary | null;
  labels: Record<string, Label>;
};
