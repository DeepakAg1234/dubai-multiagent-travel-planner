"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";

import { Check, Download, Spark, Transit, Walk } from "@/components/site/Icons";
import { Photo } from "@/components/site/Photo";
import { altFor, photoForArea, photoForPlace } from "@/lib/images";
import {
  buildDays,
  clock,
  duration,
  kindLabel,
  money,
  TRANSPORT_LABEL,
  type DayView,
  type Stop,
} from "@/lib/plan-view";
import type { Snapshot } from "@/lib/types";

import { ActivitySheet, Provenance } from "./ActivitySheet";
import { BudgetPanel } from "./BudgetPanel";

const ItineraryMap = dynamic(() => import("./ItineraryMap"), {
  ssr: false,
  loading: () => <div className="dj-map dj-skel" aria-label="Loading map" />,
});

const SUGGESTIONS = [
  "Make Day 2 less hectic",
  "Add more cultural attractions",
  "Reduce the total cost",
  "Add vegetarian restaurants",
  "Suggest experiences suitable for small children",
  "Spend more time near the beach",
];

type Props = {
  snapshot: Snapshot;
  threadId: string | null;
  busy: boolean;
  /** Short note after a re-plan, e.g. how the total moved. */
  banner: { tone: "teal" | "bad"; text: string } | null;
  changes: string[];
  onChange: (request: string) => void;
};

function constraint<T>(snapshot: Snapshot, key: string): T | undefined {
  return (snapshot.constraints as Record<string, unknown> | null)?.[key] as T | undefined;
}

function formatDate(iso?: string | null): string | null {
  if (!iso) return null;
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function TripResults({ snapshot, threadId, busy, banner, changes, onChange }: Props) {
  const plan = snapshot.final ?? snapshot.draft!;
  const labels = snapshot.labels;
  const days = useMemo(() => buildDays(plan, labels ?? {}), [plan, labels]);
  const [dayIndex, setDayIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Stop | null>(null);
  const [mapOpen, setMapOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const changeRef = useRef<HTMLInputElement>(null);
  const cardRefs = useRef<Map<string, HTMLElement>>(new Map());

  const day: DayView = days[Math.min(dayIndex, days.length - 1)];
  const budget = plan.budget ?? snapshot.budget ?? null;
  const people = constraint<number>(snapshot, "travelers");
  const interests = constraint<string[]>(snapshot, "interests") ?? [];
  const pace = constraint<string>(snapshot, "pace");
  const start = formatDate(constraint<string>(snapshot, "start_date"));
  const hotelTier = constraint<string>(snapshot, "hotel_tier");

  function pickFromMap(key: string) {
    setSelected(key);
    cardRefs.current.get(key)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function submitChange(text: string) {
    const value = text.trim();
    if (!value || busy) return;
    setDraft("");
    onChange(value);
  }

  const stopsPerDay = days.map((d) => d.mapStops.length).filter(Boolean);
  const avgStops = stopsPerDay.length ? stopsPerDay.reduce((a, b) => a + b, 0) / stopsPerDay.length : 0;
  const avgTravel = days.length ? Math.round(days.reduce((s, d) => s + d.legMinutes, 0) / days.length) : 0;
  const why: string[] = [];
  if (interests.length) why.push(`Experiences were chosen around ${interests.join(", ")}.`);
  const areas = snapshot.plan_brief?.days?.flatMap((d) => d.areas ?? []);
  if (areas?.length) why.push(`Each day is anchored in a few nearby areas (${Array.from(new Set(areas)).slice(0, 4).join(", ")}) to limit backtracking.`);
  if (avgTravel) why.push(`Planned travel between stops averages about ${avgTravel} minutes a day.`);
  if (avgStops) why.push(`About ${avgStops.toFixed(1)} stops a day, matching a ${pace ?? "balanced"} pace.`);
  if (budget?.within_budget && budget.budget_aed != null) why.push(`The estimated total of ${money(budget.total_aed)} fits within your ${money(budget.budget_aed)} budget.`);
  if (snapshot.review?.passed) why.push("The plan passed the planner\u2019s built-in review for timing and budget.");
  if (snapshot.holiday_notes?.length) why.push(snapshot.holiday_notes[0]);

  const notes = [...(plan.assumptions ?? []), ...(plan.warnings ?? [])];

  return (
    <>
      <div className="dj-wrap">
        <header className="dj-res-head dj-reveal">
          <span className="dj-eyebrow">Your itinerary</span>
          <h1>Your Personalized Dubai Adventure</h1>
          {plan.narrative ? <p className="dj-lede">{plan.narrative}</p> : null}
          <div className="dj-chips" aria-label="Trip summary">
            <span className="dj-chip">{plan.days.length} days</span>
            {start ? <span className="dj-chip">From {start}</span> : null}
            {people ? <span className="dj-chip">{people} traveler{people === 1 ? "" : "s"}</span> : null}
            {interests.length ? <span className="dj-chip">{interests.join(", ")}</span> : null}
            {pace ? <span className="dj-chip">{pace[0].toUpperCase() + pace.slice(1)} pace</span> : null}
            {hotelTier ? <span className="dj-chip">{hotelTier === "budget" ? "Affordable" : hotelTier} stay</span> : null}
          </div>
          {banner ? (
            <p className={`dj-notice ${banner.tone === "bad" ? "dj-notice--bad" : "dj-notice--teal"}`} role="status">
              {banner.text}
            </p>
          ) : null}
          {budget ? (
            <div className="dj-card dj-budget-hero">
              <div>
                <b>{money(budget.total_aed)}</b>
                <div className="dj-muted" style={{ fontSize: 14 }}>
                  estimated total{budget.budget_aed != null ? ` of ${money(budget.budget_aed)}` : ""}
                </div>
              </div>
              {budget.budget_aed != null ? (
                <div className={`dj-meter ${budget.within_budget ? "" : "is-over"}`} role="img" aria-label={`${Math.round((budget.total_aed / budget.budget_aed) * 100)} percent of your budget`}>
                  <i style={{ width: `${Math.min(100, (budget.total_aed / budget.budget_aed) * 100)}%` }} />
                </div>
              ) : (
                <span className="dj-muted" style={{ flex: 1 }} />
              )}
              <span className={`dj-pill ${budget.within_budget ? "dj-pill--ok" : "dj-pill--bad"}`}>
                {budget.within_budget ? "Within budget" : "Over budget"}
              </span>
            </div>
          ) : null}
          <div className="dj-act-row dj-noprint">
            <Link href="/plan" className="dj-btn dj-btn--ghost dj-btn--sm">
              Edit trip preferences
            </Link>
            <button type="button" className="dj-btn dj-btn--sm" onClick={() => changeRef.current?.focus()}>
              <Spark width={16} height={16} /> Request changes
            </button>
            {threadId ? (
              <>
                <a className="dj-btn dj-btn--ghost dj-btn--sm" href={`/api/planner/runs/${threadId}/export.md`}>
                  <Download width={16} height={16} /> Markdown
                </a>
                <a className="dj-btn dj-btn--ghost dj-btn--sm" href={`/api/planner/runs/${threadId}/result?download=1`}>
                  <Download width={16} height={16} /> JSON
                </a>
              </>
            ) : null}
            <button type="button" className="dj-btn dj-btn--ghost dj-btn--sm" onClick={() => window.print()}>
              Print or save as PDF
            </button>
          </div>
          <p className="dj-muted dj-noprint" style={{ fontSize: 14 }}>
            Saving and sharing a trip link are coming soon.
          </p>
        </header>
      </div>

      <div className="dj-wrap dj-layout">
        <div>
          <div className="dj-tabs-wrap dj-noprint">
            <div className="dj-tabs" role="tablist" aria-label="Days">
              {days.map((d, i) => (
                <button
                  key={d.day}
                  type="button"
                  role="tab"
                  id={`tab-${d.day}`}
                  aria-selected={i === dayIndex}
                  aria-controls="day-panel"
                  className="dj-tab"
                  onClick={() => {
                    setDayIndex(i);
                    setSelected(null);
                  }}
                >
                  Day {d.day}
                </button>
              ))}
            </div>
          </div>

          <div id="day-panel" role="tabpanel" aria-labelledby={`tab-${day.day}`} key={day.day} className="dj-reveal">
            <div className="dj-day-head">
              <span className="dj-eyebrow">Day {day.day}</span>
              <h2>{day.theme}</h2>
              <p className="dj-muted">
                {day.mapStops.length} stop{day.mapStops.length === 1 ? "" : "s"}
                {day.legMinutes ? ` \u00B7 about ${duration(day.legMinutes)} of travel between stops` : ""}
                {day.dayCost != null ? ` \u00B7 ${money(day.dayCost)} listed for attractions and meals` : ""}
              </p>
              {day.holidayNote ? <p className="dj-notice">{day.holidayNote}</p> : null}
            </div>

            <div className="dj-timeline">
              {day.stops.map((stop) => {
                const quiet = stop.kind === "checkin" || stop.kind === "checkout" || stop.kind === "rest" || stop.kind === "transfer";
                const photo = quiet ? null : photoForPlace(stop.placeId, stop.category, stop.area);
                const flagged = stop.status === "closed" || stop.status === "reopening";
                return (
                  <div key={stop.key}>
                    {stop.legIn ? (
                      <div className="dj-leg">
                        {stop.legIn.mode === "walk" ? <Walk /> : <Transit />}
                        {TRANSPORT_LABEL[stop.legIn.mode] ?? stop.legIn.mode} &middot; {stop.legIn.minutes} min
                        {stop.legIn.cost_aed != null ? ` \u00B7 ${money(stop.legIn.cost_aed)}` : ""}
                        <Provenance value={stop.legIn.provenance} />
                      </div>
                    ) : null}
                    <div className={`dj-stop ${quiet ? "dj-stop--quiet" : ""}`}>
                      <div className="dj-stop-rail">
                        <span className={`dj-num ${stop.n === null ? "dj-num--plain" : ""}`} aria-hidden={stop.n === null}>
                          {stop.n ?? ""}
                        </span>
                      </div>
                      <button
                        type="button"
                        ref={(el) => {
                          if (el) cardRefs.current.set(stop.key, el);
                        }}
                        className={`dj-card dj-act dj-hoverzoom ${selected === stop.key ? "is-sel" : ""}`}
                        onClick={() => {
                          setSelected(stop.key);
                          setDetail(stop);
                        }}
                        aria-label={`${stop.name}, ${clock(stop.start)} to ${clock(stop.end)}. Open details`}
                      >
                        {!quiet ? <Photo photo={photo} alt={altFor(photo, stop.name)} sizes="(max-width: 720px) 90vw, (max-width: 1100px) 80vw, 45vw" label={stop.name} /> : null}
                        <span className="dj-act-body">
                          <span className="dj-act-meta">
                            <b>
                              {clock(stop.start)} &ndash; {clock(stop.end)}
                            </b>
                            <span>{duration(stop.minutes)}</span>
                            <span className="dj-pill">{kindLabel(stop.kind)}</span>
                            {flagged ? <span className="dj-pill dj-pill--bad">{stop.status}</span> : null}
                          </span>
                          <h3>{stop.name}</h3>
                          {stop.area ? <span className="dj-muted" style={{ fontSize: 15 }}>{stop.area}{stop.category ? ` \u00B7 ${stop.category.replace(/_/g, " ")}` : ""}</span> : null}
                          {stop.notes ? <span className="dj-why">{stop.notes}</span> : null}
                          {stop.cost ? (
                            <span className="dj-act-meta">
                              <b>{stop.cost.total ? money(stop.cost.total) : "Free or included"}</b>
                              <Provenance value={stop.cost.provenance} />
                            </span>
                          ) : null}
                        </span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <aside className={`dj-map-col dj-noprint ${mapOpen ? "" : "is-collapsed"}`} aria-label="Map">
          <button type="button" className="dj-btn dj-btn--ghost dj-btn--sm dj-mapbtn" aria-expanded={mapOpen} onClick={() => setMapOpen((v) => !v)}>
            {mapOpen ? "Hide map" : `Show map for Day ${day.day}`}
          </button>
          {day.mapStops.length ? (
            <>
              <ItineraryMap stops={day.mapStops} selected={selected} onSelect={pickFromMap} dayKey={day.day} />
              <p className="dj-map-note">
                Numbered stops match the timeline. Dashed lines join stops in visiting order; they are not road routes.
                Map &copy; OpenStreetMap contributors.
              </p>
            </>
          ) : (
            <p className="dj-notice">No stored coordinates for this day&rsquo;s stops, so there&rsquo;s nothing to plot.</p>
          )}
        </aside>
      </div>

      <div className="dj-wrap" style={{ display: "grid", gap: 28, paddingBottom: 40 }}>
        {budget ? <BudgetPanel budget={budget} /> : null}

        {plan.stay?.name ? (
          <section className="dj-card dj-stay" aria-labelledby="stay-title">
            {(() => {
              const photo = photoForArea(plan.stay?.area);
              return <Photo photo={photo} alt={altFor(photo, `${plan.stay?.area ?? "Dubai"} neighbourhood`)} sizes="(max-width: 720px) 100vw, 240px" label={plan.stay?.area ?? ""} />;
            })()}
            <div className="dj-stay-body">
              <span className="dj-eyebrow">Where to stay</span>
              <h3 id="stay-title">{plan.stay.name}</h3>
              <p className="dj-muted">
                {[plan.stay.area, plan.stay.tier === "budget" ? "Affordable" : plan.stay.tier].filter(Boolean).join(" \u00B7 ")}
                {plan.stay.metro_nearby ? ` \u00B7 near ${plan.stay.metro_nearby} metro` : ""}
              </p>
              {plan.stay.nightly_min_aed != null && plan.stay.nightly_max_aed != null ? (
                <p>
                  About {money(plan.stay.nightly_min_aed)}&ndash;{money(plan.stay.nightly_max_aed)} a night{plan.stay.season ? ` (${plan.stay.season} season)` : ""}{" "}
                  <Provenance value={plan.stay.provenance ?? "estimated"} />
                </p>
              ) : null}
              {budget?.by_category?.accommodation ? <p>Accommodation in this plan: <b>{money(budget.by_category.accommodation)}</b></p> : null}
              <p className="dj-muted" style={{ fontSize: 14 }}>
                Chosen for its location relative to your stops. This is a catalog entry, not live availability or a booking. The photo shows the area, not the hotel.
              </p>
            </div>
          </section>
        ) : null}

        {why.length ? (
          <section className="dj-card dj-block" aria-labelledby="why-title">
            <h2 id="why-title">Why this trip works for you</h2>
            <ul className="dj-why-list">
              {why.map((line) => (
                <li key={line}>
                  <Check />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {notes.length ? (
          <details className="dj-card dj-block">
            <summary style={{ cursor: "pointer", fontWeight: 600, color: "var(--navy)", fontSize: 18 }}>Good to know ({notes.length})</summary>
            <ul style={{ margin: "12px 0 0", paddingLeft: 20, display: "grid", gap: 6 }}>
              {notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </details>
        ) : null}

        <section className="dj-card dj-change dj-noprint" aria-labelledby="change-title">
          <h2 id="change-title">Want to change something?</h2>
          <p>Tell us what to adjust. We&rsquo;ll plan again with your change added to your original request.</p>
          {changes.length ? (
            <p style={{ fontSize: 14 }}>Changes so far: {changes.map((c, i) => `${i + 1}. ${c}`).join("  ")}</p>
          ) : null}
          <div className="dj-checks">
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" className="dj-chip" disabled={busy} onClick={() => submitChange(s)}>
                {s}
              </button>
            ))}
          </div>
          <form
            className="dj-change-row"
            onSubmit={(e) => {
              e.preventDefault();
              submitChange(draft);
            }}
          >
            <input
              ref={changeRef}
              className="dj-input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="e.g. Swap the Gold Souk for something outdoors"
              aria-label="Describe a change"
              maxLength={240}
            />
            <button type="submit" className="dj-btn" disabled={busy || !draft.trim()}>
              {busy ? "Planning\u2026" : "Update my plan"}
            </button>
          </form>
          <p style={{ fontSize: 13.5 }}>
            Pace, budget, hotel category, interests and trip length are applied reliably. Other requests are read on a best-effort basis and may not change the plan.
          </p>
        </section>
      </div>

      {detail ? <ActivitySheet stop={detail} day={day} onClose={() => setDetail(null)} /> : null}
    </>
  );
}
