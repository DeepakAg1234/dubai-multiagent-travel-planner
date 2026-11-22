import type { BudgetLine, DayPlan, Itinerary, Label, Leg } from "./types";

export type Stop = {
  key: string;
  day: number;
  /** 1-based number among the day's mappable stops; null for rows that are not places. */
  n: number | null;
  kind: string;
  placeId: string | null;
  name: string;
  area: string | null;
  category: string | null;
  start: string;
  end: string;
  minutes: number;
  notes: string | null;
  status: string | null;
  lat: number | null;
  lng: number | null;
  cost: { total: number; provenance: string; item: string } | null;
  legIn: Leg | null;
};

export type DayView = {
  day: number;
  theme: string;
  holidayNote: string | null;
  stops: Stop[];
  mapStops: Stop[];
  legMinutes: number;
  dayCost: number | null;
};

const KIND_LABEL: Record<string, string> = {
  activity: "Experience",
  meal: "Meal",
  transfer: "Getting around",
  rest: "Rest",
  checkin: "Hotel check-in",
  checkout: "Hotel check-out",
};

export function kindLabel(kind: string): string {
  return KIND_LABEL[kind] ?? kind;
}

export function clock(value: string): string {
  const [h, m] = value.split(":");
  const hour = Number(h);
  if (!Number.isFinite(hour)) return value.slice(0, 5);
  const suffix = hour >= 12 ? "PM" : "AM";
  return `${hour % 12 || 12}:${m} ${suffix}`;
}

export function minutesBetween(start: string, end: string): number {
  const a = start.split(":").map(Number);
  const b = end.split(":").map(Number);
  return Math.max(0, b[0] * 60 + b[1] - (a[0] * 60 + a[1]));
}

export function duration(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h} hr ${m} min` : `${h} hr`;
}

export function money(value: number): string {
  return `AED ${Math.round(value).toLocaleString()}`;
}

function costFor(name: string, lines: BudgetLine[]): Stop["cost"] {
  if (!name) return null;
  const needle = name.toLowerCase();
  const hit = lines.find(
    (line) => (line.category === "activities" || line.category === "food") && line.item.toLowerCase().includes(needle),
  );
  return hit ? { total: hit.total_aed, provenance: hit.provenance, item: hit.item } : null;
}

export function buildDays(plan: Itinerary, labels: Record<string, Label>): DayView[] {
  const lines = plan.budget?.lines ?? [];
  return plan.days.map((day: DayPlan) => {
    let counter = 0;
    const stops: Stop[] = day.slots.map((slot, index) => {
      const label = slot.place_id ? labels[slot.place_id] : undefined;
      const mappable = Boolean(label && slot.kind !== "checkin" && slot.kind !== "checkout" && slot.kind !== "transfer");
      const n = mappable ? ++counter : null;
      const name =
        label?.name ??
        (slot.kind === "checkin" || slot.kind === "checkout"
          ? plan.stay?.name ?? kindLabel(slot.kind)
          : slot.notes ?? kindLabel(slot.kind));
      const legIn = slot.place_id ? day.legs.find((leg) => leg.to_id === slot.place_id) ?? null : null;
      return {
        key: `${day.day}-${index}`,
        day: day.day,
        n,
        kind: slot.kind,
        placeId: slot.place_id ?? null,
        name,
        area: label?.area ?? null,
        category: label?.category ?? null,
        start: slot.start.slice(0, 5),
        end: slot.end.slice(0, 5),
        minutes: minutesBetween(slot.start, slot.end),
        notes: label?.name ? slot.notes ?? null : null,
        status: label?.operational_status ?? null,
        lat: label ? label.lat : null,
        lng: label ? label.lng : null,
        cost: label ? costFor(label.name, lines) : null,
        legIn,
      };
    });
    const costs = stops.map((s) => s.cost?.total).filter((v): v is number => typeof v === "number");
    return {
      day: day.day,
      theme: day.theme,
      holidayNote: day.holiday_note ?? null,
      stops,
      mapStops: stops.filter((s) => s.n !== null && s.lat !== null),
      legMinutes: day.legs.reduce((sum, leg) => sum + leg.minutes, 0),
      dayCost: costs.length ? costs.reduce((a, b) => a + b, 0) : null,
    };
  });
}

export const CATEGORY_LABEL: Record<string, string> = {
  accommodation: "Accommodation",
  activities: "Attractions",
  food: "Food",
  transport: "Local transport",
  buffer: "Other & buffer",
};

export const PROVENANCE: Record<string, { label: string; hint: string }> = {
  verified: { label: "Verified", hint: "Checked against an official source" },
  api: { label: "Live data", hint: "Returned by a live data provider" },
  estimated: { label: "Estimated", hint: "A planning estimate, not a confirmed price" },
};

export const TRANSPORT_LABEL: Record<string, string> = {
  walk: "Walk",
  metro: "Metro",
  bus: "Bus",
  taxi: "Taxi",
  tram: "Tram",
  ferry: "Ferry",
  drive: "Drive",
};
