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

const SMALL_NUMBERS: Record<string, number> = {
  a: 1,
  an: 1,
  one: 1,
  two: 2,
  three: 3,
  four: 4,
  five: 5,
  six: 6,
  seven: 7,
  eight: 8,
  nine: 9,
  ten: 10,
};

/** Traveler steppers stop at these. A spoken count above them is clamped, not dropped. */
const MAX_ADULTS = 12;
const MAX_CHILDREN = 8;

const HINDI_LETTER = "\\u0900-\\u097F";

/** Hindi trip words the English reader already understands. Longer phrases go first. */
const HINDI_TRIP_WORDS: [string, string][] = [
  ["समुद्र\\s*तट|समुद्र", " beach "],
  ["बीचस|बीचेस|बीचेज़|बीचेज", " beach "],
  ["लोगों", " people "],
  ["लोग", " people "],
  ["बच्चों|बच्चे|बच्चा", " child "],
  ["बेटियाँ|बेटियां|बेटियों", " daughter "],
  ["बेटी", " daughter "],
  ["बेटे|बेटा", " son "],
  ["कपल्स|कपल", " couple "],
  ["हनीमून", " honeymoon "],
  ["पत्नी", " wife "],
  ["पति", " husband "],
  ["दोस्तों|दोस्त", " friends "],
  ["अकेले", " solo "],
  ["परिवार", " family "],
  ["दिनों|दिन", " days "],
  ["रातें|रात", " nights "],
  ["बजट", " budget "],
  ["संस्कृति", " culture "],
  ["इतिहास", " heritage "],
  ["खरीदारी|शॉपिंग", " shopping "],
  ["खाना|भोजन", " food "],
  ["रेगिस्तान", " desert "],
  ["सफारी", " safari "],
  ["आरामदायक|आराम", " relaxed "],
  ["किफायती|सस्ती|सस्ता", " affordable "],
  ["लग्जरी|लक्जरी", " luxury "],
  ["शाकाहारी", " vegetarian "],
  ["एक", " one "],
  ["दो", " two "],
  ["तीन", " three "],
  ["चार", " four "],
  ["पांच|पाँच", " five "],
  ["छह|छः", " six "],
  ["सात", " seven "],
  ["आठ", " eight "],
  ["नौ", " nine "],
  ["दस", " ten "],
];

const DEVANAGARI_DIGITS = "०१२३४५६७८९";

/**
 * Rewrites common Hindi trip words into the English phrases `extractFromText` already reads.
 * Bare बीच is left alone: in Hindi it means "between", while बीचस is the spoken word "beaches".
 */
export function glossTripWords(text: string): string {
  let next = text.replace(/[०-९]/g, (digit) => String(DEVANAGARI_DIGITS.indexOf(digit)));
  for (const [pattern, word] of HINDI_TRIP_WORDS) {
    next = next.replace(new RegExp(`(?<![${HINDI_LETTER}])(?:${pattern})(?![${HINDI_LETTER}])`, "g"), word);
  }
  return next;
}

function smallNumber(token: string): number | null {
  if (token in SMALL_NUMBERS) return SMALL_NUMBERS[token];
  const value = Number(token);
  if (!Number.isInteger(value) || value < 1 || value > 10) return null;
  return value;
}

function leadingCount(lower: string, unit: string): number | null {
  const match = lower.match(new RegExp(`\\b([1-9]|10|one|two|three|four|five|six|seven|eight|nine|ten|a|an)\\s+(?:${unit})\\b`));
  if (!match) return null;
  return smallNumber(match[1]);
}

function clampCount(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Best-effort, local reading of a free-text description so the fields can be pre-filled and corrected. */
export function extractFromText(text: string): { patch: Partial<Draft>; found: string[] } {
  const patch: Partial<Draft> = {};
  const found: string[] = [];
  const prepared = glossTripWords(text);
  const lower = prepared.toLowerCase();

  const days = lower.match(/\b([1-7]|one|two|three|four|five|six|seven)[\s-]*(?:days?|nights?)\b/);
  if (days) {
    patch.days = SMALL_NUMBERS[days[1]] ?? Number(days[1]);
    found.push(`${patch.days} days`);
  }
  const budget = lower.match(/(?:aed|budget(?: of)?)\s*[:=]?\s*([\d,]{3,})|([\d,]{3,})\s*aed/);
  if (budget) {
    patch.budget = (budget[1] ?? budget[2]).replace(/,/g, "");
    patch.budgetMode = /\bper person\b|\beach\b|\bpp\b/.test(lower) ? "per_person" : "total";
    found.push(`AED ${Number(patch.budget).toLocaleString()}`);
  }
  const date = text.match(/\b(20\d{2}-\d{2}-\d{2})\b/);
  if (date) {
    patch.startDate = date[1];
    found.push(`starting ${date[1]}`);
  }
  const kids = /\b(daughter|son|kids?|child(?:ren)?|toddler|baby)\b/.test(lower);
  const couple = /\b(couple|wife|husband|partner|girlfriend|boyfriend|honeymoon|romantic)\b/.test(lower);
  const childCount = leadingCount(lower, "kids?|children|child|daughters?|sons?|toddlers?|babies|baby");
  const adultCount = leadingCount(lower, "adults?");
  const peopleCount = leadingCount(lower, "people|persons|travell?ers|guests");
  if (kids) {
    patch.who = "family";
    patch.children = clampCount(childCount ?? 1, 1, MAX_CHILDREN);
    if (adultCount) patch.adults = clampCount(adultCount, 1, MAX_ADULTS);
    else if (couple || /\bwe\b|\bour\b|\bfamily\b/.test(lower)) patch.adults = 2;
    else if (peopleCount) patch.adults = clampCount(peopleCount - patch.children, 1, MAX_ADULTS);
    else patch.adults = 1;
    found.push(
      childCount == null && patch.children === 1
        ? "family trip"
        : `family, ${patch.adults} adults and ${patch.children} ${patch.children === 1 ? "child" : "children"}`,
    );
  } else if (couple) {
    patch.who = "couple";
    patch.adults = clampCount(adultCount ?? 2, 1, MAX_ADULTS);
    patch.children = 0;
    found.push("couple");
  } else if (/\b(solo|alone|by myself)\b/.test(lower) || peopleCount === 1) {
    patch.who = "solo";
    patch.adults = 1;
    patch.children = 0;
    found.push("solo");
  } else if (/\bfriends\b/.test(lower) || (peopleCount != null && peopleCount >= 3 && peopleCount < 6)) {
    patch.who = "friends";
    patch.adults = clampCount(peopleCount ?? adultCount ?? 3, 1, MAX_ADULTS);
    patch.children = 0;
    found.push(peopleCount != null && peopleCount !== 3 ? `${peopleCount} people` : "friends");
  } else if (peopleCount != null && peopleCount >= 6) {
    patch.who = "group";
    patch.adults = clampCount(peopleCount, 1, MAX_ADULTS);
    patch.children = 0;
    found.push(`${peopleCount} people`);
  } else if (peopleCount === 2) {
    patch.who = "couple";
    patch.adults = 2;
    patch.children = 0;
    found.push("couple");
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
