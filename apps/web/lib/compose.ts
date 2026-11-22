export type Overrides = {
  days: string;
  budget: string;
  interests: string;
  startDate: string;
  hotelTier: string;
  avoidCrowds: boolean;
};

export const EMPTY_OVERRIDES: Overrides = {
  days: "",
  budget: "",
  interests: "",
  startDate: "",
  hotelTier: "",
  avoidCrowds: false,
};

export function composeRequest(text: string, overrides: Overrides): string {
  const lines = [text.trim()];
  if (overrides.days.trim()) lines.push(`days: ${overrides.days.trim()}`);
  if (overrides.budget.trim()) lines.push(`AED ${overrides.budget.trim()}`);
  if (overrides.startDate.trim()) lines.push(overrides.startDate.trim());
  if (overrides.hotelTier.trim()) lines.push(`${overrides.hotelTier.trim()} hotel`);
  if (overrides.avoidCrowds) lines.push("avoid crowds");
  if (overrides.interests.trim()) lines.push(overrides.interests.trim());
  return lines.filter(Boolean).join("\n");
}

export type Preset = {
  id: string;
  label: string;
  detail: string;
  text: string;
  overrides: Overrides;
};

export const PRESETS: Preset[] = [
  {
    id: "example",
    label: "Example",
    detail: "4 days, AED 5000, culture, food, beaches",
    text: "4 days in Dubai, culture, food, and beaches, AED 5000, affordable hotel, avoid crowds",
    overrides: { ...EMPTY_OVERRIDES },
  },
  {
    id: "budget",
    label: "Tight budget",
    detail: "Luxury stay forced under a mid-tier total",
    text: "force:budget",
    overrides: { ...EMPTY_OVERRIDES },
  },
  {
    id: "museum",
    label: "Future Museum",
    detail: "Schedules the reopening Museum of the Future",
    text: "force:museum",
    overrides: { ...EMPTY_OVERRIDES },
  },
  {
    id: "eid",
    label: "Eid al-Fitr",
    detail: "Starts 2026-03-19, heritage venues and no lunch",
    text: "force:eid",
    overrides: { ...EMPTY_OVERRIDES },
  },
  {
    id: "national",
    label: "National Day",
    detail: "Starts 2026-12-02 with avoid crowds",
    text: "force:national",
    overrides: { ...EMPTY_OVERRIDES },
  },
];
