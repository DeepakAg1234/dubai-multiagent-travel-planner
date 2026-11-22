"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { Arrow, Check } from "@/components/site/Icons";
import { BudgetPanel } from "@/components/trip/BudgetPanel";
import type { AuditFinding, AuditReport } from "@/lib/audit";
import { buildDays, clock, money, TRANSPORT_LABEL, type DayView } from "@/lib/plan-view";
import type { Itinerary, Label } from "@/lib/types";

const PROMISES = [
  ["Real places", "A name has to be on our Dubai list. If a chatbot invented it, we say so."],
  ["A day you can actually walk", "We check opening hours, holiday closures, crowds, and the time between stops."],
  ["A cost that adds up", "Hotel, meals, tickets, and local transport are priced from our list, in AED."],
];

export function AuditStudio() {
  const [text, setText] = useState("");
  const [report, setReport] = useState<AuditReport | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function check(next = text) {
    const value = next.trim();
    if (value.length < 20) {
      setError("Paste a few lines of the plan, including the place names.");
      setReport(null);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/planner/audits", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text: value }),
      });
      if (!response.ok) {
        setReport(null);
        setError((await readError(response)) || "We could not check that plan. Please try again.");
        return;
      }
      setReport((await response.json()) as AuditReport);
    } catch {
      setReport(null);
      setError("We could not reach the checker. Start the planner service and try again.");
    } finally {
      setBusy(false);
    }
  }

  async function loadSample() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/planner/audits/example");
      if (!response.ok) {
        setError("The sample plan is unavailable right now.");
        setBusy(false);
        return;
      }
      const body = (await response.json()) as { text?: string };
      const sample = body.text ?? "";
      setText(sample);
      setBusy(false);
      await check(sample);
    } catch {
      setError("We could not reach the checker. Start the planner service and try again.");
      setBusy(false);
    }
  }

  const priced = report?.repaired?.budget ?? report?.original?.budget ?? null;

  return (
    <div className="dj-audit">
      <section className="dj-section" style={{ paddingTop: 48 }}>
        <div className="dj-wrap">
          <span className="dj-eyebrow">Check a plan</span>
          <h1 className="dj-h2" style={{ maxWidth: 760 }}>
            Paste a Dubai plan from ChatGPT or Claude. We will tell you what does not hold up.
          </h1>
          <p className="dj-lede" style={{ maxWidth: 680 }}>
            A chat reply can sound complete and still name places that are closed, skip the time between
            stops, or quote a budget that cannot pay for the hotel. This check uses our Dubai list, the
            metro, and the same rules as the planner. It does not book anything.
          </p>
          <ol className="dj-audit-promises">
            {PROMISES.map(([title, copy]) => (
              <li key={title}>
                <Check />
                <span>
                  <strong>{title}</strong>
                  {copy}
                </span>
              </li>
            ))}
          </ol>

          <div className="dj-card dj-audit-box">
            <label className="dj-field" htmlFor="audit-text">
              <span>The plan you were given</span>
              <textarea
                id="audit-text"
                className="dj-textarea"
                style={{ minHeight: 220 }}
                value={text}
                placeholder={"Day 1\nMorning: Museum of the Future\nAfternoon: a place name\n\nBudget AED 5000"}
                onChange={(event) => setText(event.target.value)}
              />
            </label>
            <div className="dj-audit-actions">
              <button type="button" className="dj-btn" disabled={busy} onClick={() => void check()}>
                {busy ? "Checking…" : "Check this plan"} <Arrow width={18} height={18} />
              </button>
              <button type="button" className="dj-btn dj-btn--ghost" disabled={busy} onClick={() => void loadSample()}>
                Try a sample that should fail
              </button>
              <Link href="/plan" className="dj-audit-quiet">
                Or start a plan from scratch
              </Link>
            </div>
            {error ? (
              <p className="dj-pill dj-pill--bad" role="alert">
                {error}
              </p>
            ) : null}
          </div>
        </div>
      </section>

      {report ? (
        <section className="dj-section" style={{ paddingTop: 0 }} aria-live="polite">
          <div className="dj-wrap dj-audit-result">
            <div className={`dj-verdict dj-verdict--${report.verdict}`}>
              <span className="dj-eyebrow">Result</span>
              <h2>{report.headline}</h2>
              <p>{report.summary}</p>
            </div>

            <div className="dj-audit-split">
              <article className="dj-card dj-audit-panel">
                <h3>What we recognized</h3>
                {report.recognized.length ? (
                  <ul className="dj-audit-chips">
                    {report.recognized.map((row) => (
                      <li key={`${row.kind}-${row.name}-${row.day ?? "stay"}`}>
                        {row.name}
                        <small>
                          {row.kind === "hotel" ? "Stay" : row.day ? `Day ${row.day}` : row.area}
                          {row.status && row.status !== "open" ? ` · ${row.status}` : ""}
                        </small>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>None of the names matched our Dubai list.</p>
                )}
              </article>
              <article className="dj-card dj-audit-panel">
                <h3>What we could not find</h3>
                {report.unknown.length ? (
                  <ul className="dj-audit-chips">
                    {report.unknown.map((name) => (
                      <li key={name}>
                        {name}
                        <small>Not on our list</small>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>Every name we read is on our Dubai list.</p>
                )}
              </article>
            </div>

            <IssueList title="Problems in the pasted plan" rows={report.findings} empty="No problems in the pasted plan." />

            {report.repairs.length ? (
              <article className="dj-card dj-audit-panel">
                <h3>What we changed</h3>
                <ul className="dj-audit-notes">
                  {report.repairs.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </article>
            ) : null}

            <IssueList
              title="Still needs a decision"
              rows={report.remaining}
              empty="The rebuilt plan clears the blocking checks."
            />

            <div className="dj-audit-split">
              <PlanColumn title="The plan as pasted" plan={report.original} labels={report.labels} />
              <PlanColumn title="A practical version" plan={report.repaired} labels={report.labels} />
            </div>

            {priced ? (
              <div>
                <p className="dj-eyebrow">{report.repaired ? "Cost of the practical version" : "Cost of the pasted plan"}</p>
                <BudgetPanel budget={priced} />
              </div>
            ) : null}

            <details className="dj-card dj-audit-panel">
              <summary>How to read this</summary>
              <ul className="dj-audit-notes">
                {report.assumptions.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </details>

            <p>
              <Link href="/plan" className="dj-btn">
                Build my own Dubai plan <Arrow width={18} height={18} />
              </Link>
            </p>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function IssueList({ title, rows, empty }: { title: string; rows: AuditFinding[]; empty: string }) {
  const blockers = rows.filter((row) => row.severity === "blocker");
  const warnings = rows.filter((row) => row.severity === "warning");
  return (
    <article className="dj-card dj-audit-panel">
      <h3>{title}</h3>
      {rows.length ? (
        <ul className="dj-issues">
          {[...blockers, ...warnings].map((row) => (
            <li key={`${row.code}-${row.detail}`}>
              <span className={`dj-pill ${row.severity === "blocker" ? "dj-pill--bad" : "dj-pill--warn"}`}>
                {row.severity === "blocker" ? "Needs a fix" : "Worth knowing"}
              </span>
              <strong>{row.title}</strong>
              <p>{row.detail}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p>{empty}</p>
      )}
    </article>
  );
}

function PlanColumn({
  title,
  plan,
  labels,
}: {
  title: string;
  plan: Itinerary | null;
  labels: Record<string, Label>;
}) {
  const days = useMemo(() => (plan ? buildDays(plan, labels) : []), [plan, labels]);
  return (
    <article className="dj-card dj-audit-panel">
      <h3>{title}</h3>
      {plan?.stay?.name ? (
        <p className="dj-muted">
          Stay: {plan.stay.name}
          {plan.budget ? ` · ${money(plan.budget.total_aed)} estimated` : ""}
        </p>
      ) : (
        <p className="dj-muted">No stay was attached.</p>
      )}
      {plan && days.length ? (
        days.map((day) => <DayBlock key={day.day} day={day} />)
      ) : (
        <p>Nothing usable was left to schedule.</p>
      )}
    </article>
  );
}

function DayBlock({ day }: { day: DayView }) {
  return (
    <div className="dj-audit-day">
      <h4>
        Day {day.day}
        <span>{day.theme}</span>
      </h4>
      {day.holidayNote ? <p className="dj-muted">{day.holidayNote}</p> : null}
      {day.stops.length ? (
        <ol>
          {day.stops.map((stop) => (
            <li key={stop.key}>
              <time>{clock(stop.start)}</time>
              <span>
                {stop.name}
                {stop.legIn ? (
                  <small>
                    {TRANSPORT_LABEL[stop.legIn.mode] ?? stop.legIn.mode} · {stop.legIn.minutes} min
                  </small>
                ) : null}
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="dj-muted">No stops.</p>
      )}
    </div>
  );
}

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : "";
  } catch {
    return "";
  }
}
