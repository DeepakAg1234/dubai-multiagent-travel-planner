import type { BudgetReport } from "@/lib/types";
import { CATEGORY_LABEL, money } from "@/lib/plan-view";

import { Provenance } from "./ActivitySheet";

export function BudgetPanel({ budget }: { budget: BudgetReport }) {
  const entries = Object.entries(budget.by_category).filter(([, v]) => v > 0);
  const max = Math.max(...entries.map(([, v]) => v), 1);
  const limit = budget.budget_aed ?? null;
  const diff = limit != null ? limit - budget.total_aed : null;
  const mix = new Map<string, number>();
  for (const line of budget.lines) mix.set(line.provenance, (mix.get(line.provenance) ?? 0) + line.total_aed);

  return (
    <section className="dj-card dj-block" aria-labelledby="budget-title">
      <div>
        <span className="dj-eyebrow">Budget</span>
        <h2 id="budget-title">Where your money goes</h2>
      </div>
      <div className="dj-budget-hero" style={{ padding: 0 }}>
        <div>
          <b>{money(budget.total_aed)}</b>
          <div className="dj-muted" style={{ fontSize: 14 }}>
            estimated total
          </div>
        </div>
        {limit != null ? (
          <div style={{ flex: 1, minWidth: 220 }}>
            <div className={`dj-meter ${budget.within_budget ? "" : "is-over"}`} role="img" aria-label={`${Math.round((budget.total_aed / limit) * 100)} percent of budget`}>
              <i style={{ width: `${Math.min(100, (budget.total_aed / limit) * 100)}%` }} />
            </div>
            <p style={{ marginTop: 8, fontSize: 15 }}>
              <span className={`dj-pill ${budget.within_budget ? "dj-pill--ok" : "dj-pill--bad"}`}>
                {budget.within_budget ? "Within budget" : "Over budget"}
              </span>{" "}
              {diff != null ? (diff >= 0 ? `${money(diff)} under your ${money(limit)} limit` : `${money(-diff)} over your ${money(limit)} limit`) : null}
            </p>
          </div>
        ) : null}
      </div>
      {!budget.within_budget && limit != null ? (
        <p className="dj-notice">
          This plan costs more than your budget. We&rsquo;ve kept it so you can see the tradeoff rather than hiding it.
          {budget.alternatives?.length ? " The options below could bring it down." : ""}
        </p>
      ) : null}
      <div className="dj-bars">
        {entries.map(([key, value]) => (
          <div className="dj-bar-row" key={key}>
            <span>{CATEGORY_LABEL[key] ?? key}</span>
            <div className="dj-meter">
              <i style={{ width: `${Math.max(3, (value / max) * 100)}%` }} />
            </div>
            <b>{money(value)}</b>
          </div>
        ))}
      </div>
      <p className="dj-muted" style={{ fontSize: 14 }}>
        {Array.from(mix.entries())
          .map(([k, v]) => `${money(v)} ${k === "estimated" ? "estimated" : k === "verified" ? "verified" : "from live data"}`)
          .join(" \u00B7 ")}
        . Estimates are planning figures, not quotes. Flights are not included.
      </p>
      {budget.alternatives?.length ? (
        <div className="dj-tips">
          <h3 style={{ fontSize: 20 }}>Ways to spend less</h3>
          {budget.alternatives.map((alt, i) => (
            <div className="dj-tip" key={i}>
              <span>{alt.description}</span>
              <span className="dj-pill dj-pill--ok">Save {money(alt.savings_aed)}</span>
            </div>
          ))}
        </div>
      ) : null}
      <details>
        <summary style={{ cursor: "pointer", fontWeight: 600, color: "var(--navy)", minHeight: 40 }}>See every line</summary>
        <div style={{ overflowX: "auto" }}>
          <table className="dj-lines">
            <thead>
              <tr>
                <th>Item</th>
                <th>Type</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {budget.lines.map((line, i) => (
                <tr key={`${i}-${line.item}`}>
                  <td>
                    {line.item}
                    <div className="dj-muted" style={{ fontSize: 13 }}>
                      {CATEGORY_LABEL[line.category] ?? line.category} <Provenance value={line.provenance} />
                    </div>
                  </td>
                  <td>{line.quantity !== 1 ? `${line.quantity} \u00D7 ${money(line.unit_aed)}` : ""}</td>
                  <td>{money(line.total_aed)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
