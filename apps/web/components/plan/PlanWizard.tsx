"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { Arrow, Back, Check, Family, Group, Heart, Spark, User, Users } from "@/components/site/Icons";
import { Photo } from "@/components/site/Photo";
import { altFor, INTERESTS, pick, photoForInterest } from "@/lib/images";
import {
  composeRequest,
  EMPTY_DRAFT,
  draftRaw,
  extractFromText,
  MAX_DAYS,
  parseDraft,
  saveDraft,
  saveSession,
  subscribeStorage,
  totalBudget,
  travelers,
  validate,
  type BudgetMode,
  type Draft,
  type Who,
} from "@/lib/trip";

const STEPS = ["Dates", "Travelers", "Budget", "Interests", "Style"] as const;
const SIDE = [
  ["dubai-marina", "palm-jumeirah", "downtown-dubai"],
  ["jumeirah-beach", "dubai-marina"],
  ["the-dubai-mall", "dubai-fountain", "downtown-dubai"],
  ["museum-of-the-future", "burj-khalifa"],
  ["palm-jumeirah", "dubai-marina"],
];
const WHO: { id: Who; label: string; icon: typeof User; adults: number; children: number }[] = [
  { id: "solo", label: "Solo", icon: User, adults: 1, children: 0 },
  { id: "couple", label: "Couple", icon: Heart, adults: 2, children: 0 },
  { id: "family", label: "Family", icon: Family, adults: 2, children: 1 },
  { id: "friends", label: "Friends", icon: Users, adults: 3, children: 0 },
  { id: "group", label: "Group", icon: Group, adults: 6, children: 0 },
];
const DIET = ["Vegetarian", "Vegan", "Halal", "Gluten-free"];
const BUDGET_IDEAS = [2500, 5000, 8000, 12000];

function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function Stepper({ value, min, max, onChange, label }: { value: number; min: number; max: number; onChange: (n: number) => void; label: string }) {
  return (
    <div className="dj-stepper" role="group" aria-label={label}>
      <button type="button" aria-label={`Fewer ${label}`} disabled={value <= min} onClick={() => onChange(value - 1)}>
        &minus;
      </button>
      <output aria-live="polite">{value}</output>
      <button type="button" aria-label={`More ${label}`} disabled={value >= max} onClick={() => onChange(value + 1)}>
        +
      </button>
    </div>
  );
}

/**
 * Restores earlier answers (so Back from the itinerary keeps them) and applies a category
 * picked on the landing page. Reads storage only after hydration.
 */
export function PlanWizard() {
  const params = useSearchParams();
  const raw = useSyncExternalStore(subscribeStorage, draftRaw, () => undefined);
  const interest = params.get("interest");
  const initial = useMemo(() => {
    if (raw === undefined) return null;
    const saved = parseDraft(raw);
    let draft: Draft = saved ? { ...EMPTY_DRAFT, ...saved.draft } : EMPTY_DRAFT;
    if (interest && INTERESTS.some((i) => i.id === interest) && !draft.interests.includes(interest)) {
      draft = { ...draft, interests: [...draft.interests, interest] };
    }
    return { draft, step: saved?.step ?? 0 };
    // Wizard keeps its own state after mount, so later storage writes don't reset it.
  }, [raw, interest]);
  if (!initial) return <div className="dj-center">Loading&hellip;</div>;
  return <Wizard initialDraft={initial.draft} initialStep={initial.step} />;
}

function Wizard({ initialDraft, initialStep }: { initialDraft: Draft; initialStep: number }) {
  const router = useRouter();
  const [draft, setDraft] = useState<Draft>(initialDraft);
  const [step, setStep] = useState(initialStep);
  const [error, setError] = useState("");
  const [text, setText] = useState("");
  const [found, setFound] = useState<string[] | null>(null);

  useEffect(() => {
    saveDraft(draft, step);
  }, [draft, step]);

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }));
  const total = totalBudget(draft);
  const side = pick(...SIDE[step]);

  const summary = useMemo(() => {
    const chips: string[] = [];
    if (step > 0) chips.push(`${draft.days} days${draft.startDate && !draft.flexibleDates ? ` from ${draft.startDate}` : ""}`);
    if (step > 1) chips.push(`${draft.adults} adult${draft.adults === 1 ? "" : "s"}${draft.children ? ` + ${draft.children} child${draft.children === 1 ? "" : "ren"}` : ""}`);
    if (step > 2) chips.push(total && draft.budgetMode !== "unsure" ? `AED ${total.toLocaleString()} total` : "Budget not set");
    if (step > 3 && draft.interests.length) chips.push(`${draft.interests.length} interests`);
    return chips;
  }, [step, draft, total]);

  function stepProblem(): string {
    if (step === 0) {
      if (draft.days < 1 || draft.days > MAX_DAYS) return `Trips can be 1 to ${MAX_DAYS} days long.`;
      if (draft.startDate && !draft.flexibleDates && draft.startDate < today()) return "Pick a start date that isn\u2019t in the past, or choose flexible dates.";
    }
    if (step === 2) {
      if (draft.budgetMode !== "unsure" && draft.budget.trim() && total === null) return "Enter your budget as a number, or choose \u201CNot decided\u201D.";
    }
    return "";
  }

  function next() {
    const problem = stepProblem();
    setError(problem);
    if (problem) return;
    setStep((s) => Math.min(STEPS.length - 1, s + 1));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function submit() {
    const problems = validate(draft);
    if (problems.length) {
      setError(problems[0]);
      return;
    }
    saveSession({ draft, request: composeRequest(draft), changes: [], startedAt: Date.now() });
    router.push("/trip");
  }

  function readText() {
    const { patch, found: items } = extractFromText(text);
    if (!items.length) {
      setFound([]);
      return;
    }
    setDraft((d) => ({ ...d, ...patch, notes: d.notes || text.trim() }));
    setFound(items);
  }

  const last = step === STEPS.length - 1;

  return (
    <div className="dj-plan">
      <aside className="dj-plan-side" aria-hidden="true">
        <Photo photo={side} alt={altFor(side, "Dubai")} sizes="(max-width: 1100px) 100vw, 40vw" priority label="" />
        <p className="dj-plan-quote">
          A good Dubai trip balances the famous with the quiet.
          <small>{side ? `Photo: ${side.credit.author}, ${side.credit.license}` : ""}</small>
        </p>
      </aside>

      <div>
        <div className="dj-plan-main">
          <div className="dj-topbar">
            <Link href="/" className="dj-brand" style={{ color: "var(--navy)" }}>
              Dubai Journey AI
            </Link>
            <Link href="/audit" style={{ fontSize: 14, fontWeight: 600, color: "var(--teal-dark)" }}>
              Check a ChatGPT plan
            </Link>
            <Link href="/" className="dj-btn dj-btn--ghost dj-btn--sm">
              Exit
            </Link>
          </div>

          <div>
            <div className="dj-stepmeta">
              <span>
                Step {step + 1} of {STEPS.length}
              </span>
              <span>{STEPS[step]}</span>
            </div>
            <div className="dj-progress" role="progressbar" aria-valuemin={1} aria-valuemax={STEPS.length} aria-valuenow={step + 1} aria-label="Planning steps">
              <i style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
            </div>
          </div>

          {summary.length ? (
            <div className="dj-summary" aria-label="Your answers so far">
              {summary.map((c) => (
                <span className="dj-chip" key={c}>
                  <Check width={14} height={14} /> {c}
                </span>
              ))}
            </div>
          ) : null}

          <details className="dj-card dj-nl">
            <summary>
              <Spark width={20} height={20} /> Or describe your trip in your own words
            </summary>
            <p className="dj-muted" style={{ fontSize: 15 }}>
              Example: &ldquo;Four days in Dubai with my wife and daughter, AED 5,000 budget, culture and beaches,
              affordable hotel, relaxed pace.&rdquo;
            </p>
            <textarea
              className="dj-textarea"
              value={text}
              onChange={(e) => setText(e.target.value)}
              aria-label="Describe your trip"
              placeholder="Tell us about your trip"
            />
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
              <button type="button" className="dj-btn dj-btn--sm" onClick={readText} disabled={!text.trim()}>
                Fill in my details
              </button>
              <span className="dj-muted" style={{ fontSize: 14 }}>
                We&rsquo;ll fill in what we can find. Check each step and edit anything.
              </span>
            </div>
            {found && found.length > 0 ? (
              <div className="dj-notice dj-notice--teal" role="status">
                <b>We picked up:</b>
                <div className="dj-found" style={{ marginTop: 8 }}>
                  {found.map((f) => (
                    <span className="dj-pill dj-pill--teal" key={f}>
                      {f}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
            {found && found.length === 0 ? (
              <p className="dj-notice" role="status">
                We couldn&rsquo;t pick out any details. Try adding days, budget or interests, or use the steps below.
              </p>
            ) : null}
          </details>

          <section className="dj-q" aria-live="polite">
            {step === 0 ? (
              <div style={{ display: "grid", gap: 20 }}>
                <div>
                  <span className="dj-eyebrow">Dates</span>
                  <h1>When are you visiting Dubai?</h1>
                  <p className="dj-lede">Not sure yet? Choose flexible dates and we&rsquo;ll plan around a typical start.</p>
                </div>
                <div className="dj-grid2">
                  <label className="dj-field">
                    <span>Start date</span>
                    <input
                      className="dj-input"
                      type="date"
                      min={today()}
                      value={draft.startDate}
                      disabled={draft.flexibleDates}
                      onChange={(e) => set("startDate", e.target.value)}
                    />
                  </label>
                  <div className="dj-field">
                    <span id="days-l">How many days?</span>
                    <Stepper value={draft.days} min={1} max={MAX_DAYS} label="days" onChange={(n) => set("days", n)} />
                    <small>Trips of 1 to {MAX_DAYS} days.</small>
                  </div>
                </div>
                <label className="dj-switch">
                  <input type="checkbox" checked={draft.flexibleDates} onChange={(e) => set("flexibleDates", e.target.checked)} />
                  <span>My dates are flexible or not decided</span>
                </label>
                {draft.flexibleDates ? (
                  <p className="dj-notice dj-notice--teal">
                    Without a date, the planner assumes a typical mid-November start. Seasonal and holiday notes will
                    reflect that, not your real dates.
                  </p>
                ) : null}
                <div className="dj-grid2">
                  <label className="dj-field">
                    <span>Arrival time (optional)</span>
                    <input className="dj-input" type="time" value={draft.arrival} onChange={(e) => set("arrival", e.target.value)} />
                  </label>
                  <label className="dj-field">
                    <span>Departure time (optional)</span>
                    <input className="dj-input" type="time" value={draft.departure} onChange={(e) => set("departure", e.target.value)} />
                    <small>Shared with the planner as a note.</small>
                  </label>
                </div>
              </div>
            ) : null}

            {step === 1 ? (
              <div style={{ display: "grid", gap: 20 }}>
                <div>
                  <span className="dj-eyebrow">Travelers</span>
                  <h1>Who&rsquo;s coming along?</h1>
                </div>
                <div className="dj-who" role="radiogroup" aria-label="Who is traveling">
                  {WHO.map(({ id, label, icon: Icon, adults, children }) => (
                    <button
                      key={id}
                      type="button"
                      role="radio"
                      aria-checked={draft.who === id}
                      className="dj-opt"
                      onClick={() => setDraft((d) => ({ ...d, who: id, adults, children, childAges: children ? d.childAges : "" }))}
                    >
                      <Icon />
                      {label}
                    </button>
                  ))}
                </div>
                <div className="dj-grid2">
                  <div className="dj-field">
                    <span>Adults</span>
                    <Stepper value={draft.adults} min={1} max={12} label="adults" onChange={(n) => set("adults", n)} />
                  </div>
                  <div className="dj-field">
                    <span>Children</span>
                    <Stepper value={draft.children} min={0} max={8} label="children" onChange={(n) => set("children", n)} />
                  </div>
                </div>
                {draft.children > 0 ? (
                  <label className="dj-field">
                    <span>Children&rsquo;s ages (optional)</span>
                    <input className="dj-input" value={draft.childAges} placeholder="e.g. 4 and 9" onChange={(e) => set("childAges", e.target.value)} />
                    <small>Shared with the planner as a note.</small>
                  </label>
                ) : null}
              </div>
            ) : null}

            {step === 2 ? (
              <div style={{ display: "grid", gap: 20 }}>
                <div>
                  <span className="dj-eyebrow">Budget</span>
                  <h1>What&rsquo;s your ideal trip budget?</h1>
                  <p className="dj-lede">The planner works in AED and treats the budget as the group total, hotel included. Flights are not counted.</p>
                </div>
                <div className="dj-radio-list" role="radiogroup" aria-label="How is the budget counted">
                  {(
                    [
                      ["total", "Total for everyone", "One number for the whole group"],
                      ["per_person", "Per person", `We\u2019ll multiply by ${travelers(draft)} traveler${travelers(draft) === 1 ? "" : "s"}`],
                      ["unsure", "Not decided", "We\u2019ll plan with a default and show what it costs"],
                    ] as [BudgetMode, string, string][]
                  ).map(([id, label, hint]) => (
                    <button key={id} type="button" role="radio" aria-checked={draft.budgetMode === id} className="dj-opt" onClick={() => set("budgetMode", id)}>
                      {label}
                      <small>{hint}</small>
                    </button>
                  ))}
                </div>
                {draft.budgetMode !== "unsure" ? (
                  <>
                    <label className="dj-field">
                      <span>Budget in AED</span>
                      <input
                        className="dj-input"
                        inputMode="numeric"
                        placeholder="5000"
                        value={draft.budget}
                        onChange={(e) => set("budget", e.target.value)}
                      />
                      {draft.budgetMode === "per_person" && total ? <small>That&rsquo;s AED {total.toLocaleString()} for {travelers(draft)}.</small> : null}
                    </label>
                    <div className="dj-checks" aria-label="Budget ideas">
                      {BUDGET_IDEAS.map((n) => (
                        <button
                          key={n}
                          type="button"
                          className="dj-chip"
                          aria-pressed={Number(draft.budget) === n}
                          onClick={() => set("budget", String(n))}
                        >
                          AED {n.toLocaleString()}
                        </button>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="dj-notice dj-notice--teal">We&rsquo;ll plan against a default of AED 5,000 and show the real total.</p>
                )}
              </div>
            ) : null}

            {step === 3 ? (
              <div style={{ display: "grid", gap: 20 }}>
                <div>
                  <span className="dj-eyebrow">Interests</span>
                  <h1>What would make this trip unforgettable?</h1>
                  <p className="dj-lede">Choose as many as you like.</p>
                </div>
                <div className="dj-interests">
                  {INTERESTS.map((item) => {
                    const photo = photoForInterest(item.id);
                    const on = draft.interests.includes(item.id);
                    return (
                      <button
                        key={item.id}
                        type="button"
                        className="dj-int"
                        aria-pressed={on}
                        onClick={() => set("interests", on ? draft.interests.filter((i) => i !== item.id) : [...draft.interests, item.id])}
                      >
                        <Photo photo={photo} alt="" sizes="(max-width: 720px) 45vw, 20vw" label={item.label} />
                        <span className="dj-int-check">
                          <Check />
                        </span>
                        <span className="dj-int-t">{item.label}</span>
                      </button>
                    );
                  })}
                </div>
                {draft.interests.some((i) => i === "luxury" || i === "hidden") ? (
                  <p className="dj-notice">
                    Luxury and hidden gems are passed to the planner as notes. The catalog&rsquo;s built-in interest
                    categories are the others.
                  </p>
                ) : null}
              </div>
            ) : null}

            {step === 4 ? (
              <div style={{ display: "grid", gap: 22 }}>
                <div>
                  <span className="dj-eyebrow">Travel style</span>
                  <h1>How do you like to explore?</h1>
                </div>
                <div className="dj-radio-list" role="radiogroup" aria-label="Pace">
                  {(
                    [
                      ["relaxed", "Relaxed and easy", "Fewer stops, more time at each"],
                      ["balanced", "Balanced", "A mix of highlights and downtime"],
                      ["packed", "Packed with experiences", "See as much as possible"],
                    ] as const
                  ).map(([id, label, hint]) => (
                    <button key={id} type="button" role="radio" aria-checked={draft.pace === id} className="dj-opt" onClick={() => set("pace", id)}>
                      {label}
                      <small>{hint}</small>
                    </button>
                  ))}
                </div>
                <div className="dj-grid2">
                  <label className="dj-field">
                    <span>Hotel category</span>
                    <select className="dj-select" value={draft.hotel} onChange={(e) => set("hotel", e.target.value as Draft["hotel"])}>
                      <option value="">No preference</option>
                      <option value="budget">Affordable</option>
                      <option value="mid">Mid-range</option>
                      <option value="luxury">Luxury</option>
                    </select>
                  </label>
                  <label className="dj-switch" style={{ alignSelf: "end" }}>
                    <input type="checkbox" checked={draft.avoidCrowds} onChange={(e) => set("avoidCrowds", e.target.checked)} />
                    <span>Avoid crowds where possible</span>
                  </label>
                </div>
                <div className="dj-field">
                  <span>Dietary needs (optional)</span>
                  <div className="dj-checks">
                    {DIET.map((d) => {
                      const on = draft.dietary.includes(d.toLowerCase());
                      return (
                        <button
                          key={d}
                          type="button"
                          className="dj-chip"
                          aria-pressed={on}
                          onClick={() => set("dietary", on ? draft.dietary.filter((x) => x !== d.toLowerCase()) : [...draft.dietary, d.toLowerCase()])}
                        >
                          {d}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div className="dj-grid2">
                  <label className="dj-field">
                    <span>Must-visit places (optional)</span>
                    <input className="dj-input" value={draft.mustVisit} placeholder="e.g. Burj Khalifa" onChange={(e) => set("mustVisit", e.target.value)} />
                  </label>
                  <label className="dj-field">
                    <span>Places to skip (optional)</span>
                    <input className="dj-input" value={draft.avoid} placeholder="e.g. malls" onChange={(e) => set("avoid", e.target.value)} />
                  </label>
                </div>
                <label className="dj-field">
                  <span>Anything else we should know?</span>
                  <textarea
                    className="dj-textarea"
                    value={draft.notes}
                    placeholder="I prefer cultural experiences in the morning and don't want to spend too much time traveling between attractions."
                    onChange={(e) => set("notes", e.target.value)}
                  />
                  <small>Hotel category, pace, crowds and interests shape the plan. Other notes are read on a best-effort basis.</small>
                </label>
              </div>
            ) : null}
          </section>
          {error ? (
            <p className="dj-error" role="alert">
              {error}
            </p>
          ) : null}
        </div>
      </div>

      <div className="dj-actions">
        <div className="dj-actions-in">
          <button
            type="button"
            className="dj-btn dj-btn--ghost"
            onClick={() => {
              setError("");
              setStep((s) => Math.max(0, s - 1));
            }}
            disabled={step === 0}
          >
            <Back width={18} height={18} /> Back
          </button>
          {step === 3 ? <span className="dj-note">{draft.interests.length} selected</span> : <span className="dj-note" />}
          {last ? (
            <button type="button" className="dj-btn" onClick={submit}>
              Create My Dubai Itinerary <Arrow width={18} height={18} />
            </button>
          ) : (
            <button type="button" className="dj-btn" onClick={next}>
              Continue <Arrow width={18} height={18} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
