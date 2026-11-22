/** The traveler's answers, how they become one planner request, and what we persist. */

export type Who = "solo" | "couple" | "family" | "friends" | "group";
export type Pace = "relaxed" | "balanced" | "packed";
export type HotelTier = "" | "budget" | "mid" | "luxury";
export type BudgetMode = "total" | "per_person" | "unsure";

export type Draft = {
  startDate: string;
  days: number;
  flexibleDates: boolean;
  arrival: string;
  departure: string;
  who: Who;
  adults: number;
  children: number;
  childAges: string;
  budget: string;
  budgetMode: BudgetMode;
  interests: string[];
  pace: Pace;
  hotel: HotelTier;
  avoidCrowds: boolean;
  dietary: string[];
  mustVisit: string;
  avoid: string;
  notes: string;
};

export const EMPTY_DRAFT: Draft = {
  startDate: "",
  days: 4,
  flexibleDates: false,
  arrival: "",
  departure: "",
  who: "couple",
  adults: 2,
  children: 0,
  childAges: "",
  budget: "",
  budgetMode: "total",
  interests: [],
  pace: "balanced",
  hotel: "",
  avoidCrowds: false,
  dietary: [],
  mustVisit: "",
  avoid: "",
  notes: "",
};

/** Interest cards to the words the planner understands. Unmapped ones travel as plain text. */
const INTEREST_WORDS: Record<string, string[]> = {
  iconic: ["landmark"],
  culture: ["culture"],
  desert: ["outdoor"],
  beaches: ["beaches"],
  food: ["food"],
  family: ["family"],
  shopping: ["shopping"],
  architecture: ["landmark", "culture"],
  luxury: [],
  hidden: [],
};

export const MAX_DAYS = 7;

export function travelers(draft: Draft): number {
  return Math.max(1, draft.adults + draft.children);
}

/** The planner treats the budget as the group total including accommodation. */
export function totalBudget(draft: Draft): number | null {
  const value = Number(draft.budget.replace(/[, ]/g, ""));
  if (!Number.isFinite(value) || value <= 0) return null;
  return Math.round(draft.budgetMode === "per_person" ? value * travelers(draft) : value);
}

export function validate(draft: Draft): string[] {
  const problems: string[] = [];
  if (draft.days < 1 || draft.days > MAX_DAYS) problems.push(`Trips can be 1 to ${MAX_DAYS} days long.`);
  if (draft.startDate && !/^\d{4}-\d{2}-\d{2}$/.test(draft.startDate)) problems.push("Enter a valid start date.");
  if (draft.adults < 1) problems.push("At least one adult is needed.");
  if (draft.budgetMode !== "unsure" && draft.budget.trim() && totalBudget(draft) === null)
    problems.push("Enter your budget as a number, or choose \u201CNot decided\u201D.");
  return problems;
}

export function composeRequest(draft: Draft): string {
  const parts: string[] = [`${draft.days} days in Dubai`];
  if (draft.startDate && !draft.flexibleDates) parts.push(`starting ${draft.startDate}`);
  const total = draft.budgetMode === "unsure" ? null : totalBudget(draft);
  if (total) parts.push(`AED ${total}`);
  if (draft.hotel) parts.push(`${draft.hotel === "budget" ? "affordable" : draft.hotel} hotel`);
  const words = new Set<string>();
  for (const id of draft.interests) for (const word of INTEREST_WORDS[id] ?? []) words.add(word);
  if (words.size) parts.push(Array.from(words).join(" "));
  parts.push(`${draft.pace} pace`);
  if (draft.avoidCrowds) parts.push("avoid crowds");

  const lines = [parts.join(", ")];
  const people = [`${draft.adults} adult${draft.adults === 1 ? "" : "s"}`];
  if (draft.children) people.push(`${draft.children} child${draft.children === 1 ? "" : "ren"}${draft.childAges.trim() ? ` aged ${draft.childAges.trim()}` : ""}`);
  lines.push(`${travelers(draft)} travelers: ${people.join(" and ")} (${draft.who})`);
  const extra = draft.interests.filter((id) => !(INTEREST_WORDS[id] ?? []).length);
  if (extra.length) lines.push(`Also interested in: ${extra.map((id) => (id === "hidden" ? "hidden gems" : id)).join(", ")}`);
  const times = [draft.arrival && `arriving ${draft.arrival}`, draft.departure && `departing ${draft.departure}`].filter(Boolean);
  if (times.length) lines.push(`Flight times: ${times.join(", ")}`);
  if (draft.dietary.length) lines.push(`Dietary needs: ${draft.dietary.join(", ")}`);
  if (draft.mustVisit.trim()) lines.push(`Must visit: ${draft.mustVisit.trim()}`);
  if (draft.avoid.trim()) lines.push(`Prefer to skip: ${draft.avoid.trim()}`);
  if (draft.notes.trim()) lines.push(draft.notes.trim());
  return lines.join("\n");
}

/** Best-effort, local reading of a free-text description so the fields can be pre-filled and corrected. */
export function extractFromText(text: string): { patch: Partial<Draft>; found: string[] } {
  const patch: Partial<Draft> = {};
  const found: string[] = [];
  const lower = text.toLowerCase();
  const words: Record<string, number> = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7 };

  const days = lower.match(/\b([1-7]|one|two|three|four|five|six|seven)[\s-]*(?:days?|nights?)\b/);
  if (days) {
    patch.days = words[days[1]] ?? Number(days[1]);
    found.push(`${patch.days} days`);
  }
  const budget = lower.match(/(?:aed|budget(?: of)?)\s*[:=]?\s*([\d,]{3,})|([\d,]{3,})\s*aed/);
  if (budget) {
    patch.budget = (budget[1] ?? budget[2]).replace(/,/g, "");
    patch.budgetMode = /per person|each|pp\b/.test(lower) ? "per_person" : "total";
    found.push(`AED ${Number(patch.budget).toLocaleString()}`);
  }
  const date = text.match(/\b(20\d{2}-\d{2}-\d{2})\b/);
  if (date) {
    patch.startDate = date[1];
    found.push(`starting ${date[1]}`);
  }
  const kids = /\b(daughter|son|kids?|child(?:ren)?|toddler|baby)\b/.test(lower);
  const partner = /\b(wife|husband|partner|girlfriend|boyfriend|honeymoon|romantic)\b/.test(lower);
  if (kids) {
    patch.who = "family";
    patch.adults = partner || /\bwe\b|\bour\b|\bfamily\b/.test(lower) ? 2 : 1;
    patch.children = 1;
    found.push("family trip");
  } else if (partner || /\bcouple\b/.test(lower)) {
    patch.who = "couple";
    patch.adults = 2;
    found.push("couple");
  } else if (/\b(solo|alone|by myself)\b/.test(lower)) {
    patch.who = "solo";
    patch.adults = 1;
    found.push("solo");
  } else if (/\bfriends\b/.test(lower)) {
    patch.who = "friends";
    found.push("friends");
  }
  const interests: string[] = [];
  const rules: [string, RegExp][] = [
    ["culture", /cultur|heritage|histor/],
    ["beaches", /beach|sea\b|coast/],
    ["food", /food|restaurant|dining|cuisine/],
    ["desert", /desert|safari|dune/],
    ["shopping", /shop|mall|souk/],
    ["family", /family|kids|children/],
    ["iconic", /iconic|landmark|burj/],
    ["architecture", /architect/],
    ["luxury", /luxur/],
    ["hidden", /hidden gem|off the beaten/],
  ];
  for (const [id, pattern] of rules) if (pattern.test(lower)) interests.push(id);
  if (interests.length) {
    patch.interests = interests;
    found.push(`interests: ${interests.join(", ")}`);
  }
  if (/\b(relaxed|slow|easy|leisurely)\b/.test(lower)) {
    patch.pace = "relaxed";
    found.push("relaxed pace");
  } else if (/\b(packed|busy|action|as much as possible)\b/.test(lower)) {
    patch.pace = "packed";
    found.push("packed pace");
  }
  if (/\b(affordable|cheap|budget hotel|inexpensive)\b/.test(lower)) {
    patch.hotel = "budget";
    found.push("affordable hotel");
  } else if (/\bluxury hotel|5[- ]star\b/.test(lower)) {
    patch.hotel = "luxury";
    found.push("luxury hotel");
  } else if (/\bmid[- ](?:range|tier)\b/.test(lower)) {
    patch.hotel = "mid";
    found.push("mid-range hotel");
  }
  if (/avoid (?:the )?crowds|quiet|not crowded/.test(lower)) {
    patch.avoidCrowds = true;
    found.push("avoid crowds");
  }
  if (/vegetarian/.test(lower)) {
    patch.dietary = ["vegetarian"];
    found.push("vegetarian");
  }
  return { patch, found };
}

const KEY = "dj.session";

export type Session = {
  draft: Draft;
  request: string;
  /** Optional change requests layered on top of the original request. */
  changes: string[];
  startedAt: number;
};

const EVENT = "dj-storage";

export function saveSession(session: Session): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(session));
    window.dispatchEvent(new Event(EVENT));
  } catch {
    /* storage can be unavailable (private mode); the trip page then asks to start over */
  }
}

/** External-store hooks so components can read sessionStorage without hydration mismatches. */
export function subscribeStorage(callback: () => void): () => void {
  window.addEventListener(EVENT, callback);
  return () => window.removeEventListener(EVENT, callback);
}

/** Raw JSON, or "" when empty. Strings compare by value, so this is a stable snapshot. */
export function sessionRaw(): string {
  try {
    return sessionStorage.getItem(KEY) ?? "";
  } catch {
    return "";
  }
}

export function parseSession(raw: string): Session | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

const DRAFT_KEY = "dj.draft";
export function draftRaw(): string {
  try {
    return sessionStorage.getItem(DRAFT_KEY) ?? "";
  } catch {
    return "";
  }
}
export function parseDraft(raw: string): { draft: Draft; step: number } | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as { draft: Draft; step: number };
  } catch {
    return null;
  }
}
export function saveDraft(draft: Draft, step: number): void {
  try {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ draft, step }));
  } catch {
    /* ignore */
  }
}
