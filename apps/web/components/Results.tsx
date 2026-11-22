import type { Itinerary, Label, Snapshot } from "@/lib/types";

export type ResultTab = "itinerary" | "budget" | "notes" | "map";

export function Results({
  snapshot,
  tab,
}: {
  snapshot: Snapshot | null;
  tab: ResultTab;
}) {
  const plan = snapshot?.final ?? snapshot?.draft ?? null;
  if (!plan) return <p className="note">The itinerary appears when sequencing finishes.</p>;
  if (tab === "budget") return <Budget plan={plan} />;
  if (tab === "notes") return <Notes plan={plan} />;
  if (tab === "map") return <MapPlan plan={plan} labels={snapshot?.labels ?? {}} />;
  return <Days plan={plan} labels={snapshot?.labels ?? {}} />;
}

function Days({ plan, labels }: { plan: Itinerary; labels: Record<string, Label> }) {
  return (
    <div>
      {plan.narrative ? <p className="narrative">{plan.narrative}</p> : null}
      {plan.stay?.name ? (
        <div className="stay">
          <span className="stay-icon" aria-hidden="true">🏨</span>
          <div>
            <p className="stay-name">{plan.stay.name}</p>
            <p className="note">
              {[plan.stay.area, plan.stay.tier].filter(Boolean).join(" · ") || "Your stay"}
            </p>
          </div>
        </div>
      ) : null}
      <div className="days">
        {plan.days.map((day) => (
          <article className="day" key={day.day}>
            <p className="day-label">Day {day.day}</p>
            <h3>{day.theme}</h3>
            {day.holiday_note ? <p className="holiday">{day.holiday_note}</p> : null}
            {day.slots.map((slot, index) => {
              const label = slot.place_id ? labels[slot.place_id] : undefined;
              const status = label?.operational_status;
              const flagged = status === "closed" || status === "reopening";
              return (
                <p className="slot" key={`${day.day}-${slot.start}-${index}`}>
                  <span className="slot-time">
                    {clock(slot.start)}–{clock(slot.end)}
                  </span>
                  <span>
                    <span className="slot-kind">{slot.kind}</span> · {label?.name ?? slot.notes ?? slot.kind}
                    {slot.notes && label?.name ? <span className="note"> · {slot.notes}</span> : null}
                    {flagged ? <span className="status-flag"> · {status}</span> : null}
                  </span>
                </p>
              );
            })}
            {day.legs.length ? (
              <div className="legs">
                {day.legs.map((leg, index) => (
                  <p className="leg" key={`${day.day}-leg-${index}`}>
                    {leg.mode} · {leg.minutes} min
                    {leg.cost_aed != null ? ` · AED ${leg.cost_aed}` : ""} <Badge provenance={leg.provenance} />
                  </p>
                ))}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </div>
  );
}

function Budget({ plan }: { plan: Itinerary }) {
  const budget = plan.budget;
  if (!budget) return <p className="note">The budget is still being totaled.</p>;
  const max = Math.max(...Object.values(budget.by_category), 1);
  return (
    <div>
      <div className="total">
        <p className="total-figure">
          <small>AED</small>
          {budget.total_aed.toLocaleString()}
        </p>
        <div>
          {budget.budget_aed != null ? (
            <p className="total-meta">of AED {budget.budget_aed.toLocaleString()} budget</p>
          ) : null}
          <span className={`pill-status ${budget.within_budget ? "ok" : "over"}`}>
            {budget.within_budget ? "Within budget" : "Over budget"}
          </span>
        </div>
      </div>
      <div className="bars" aria-label="Budget by category">
        {Object.entries(budget.by_category).map(([category, amount]) => (
          <div className="bar-row" key={category}>
            <span>{category}</span>
            <div className="bar" style={{ width: `${Math.max(4, (amount / max) * 100)}%` }} />
            <span>AED {amount}</span>
          </div>
        ))}
      </div>
      <table>
        <thead>
          <tr>
            <th>Category</th>
            <th>Item</th>
            <th>Total</th>
            <th>Provenance</th>
          </tr>
        </thead>
        <tbody>
          {budget.lines.map((line, index) => (
            <tr key={`${index}-${line.category}-${line.item}`}>
              <td>{line.category}</td>
              <td>{line.item}</td>
              <td>AED {line.total_aed}</td>
              <td>
                <Badge provenance={line.provenance} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Notes({ plan }: { plan: Itinerary }) {
  return (
    <div className="stack">
      <section>
        <h3>Assumptions</h3>
        <ul>
          {(plan.assumptions ?? []).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
      <section>
        <h3>Warnings</h3>
        {(plan.warnings ?? []).length ? (
          <ul>
            {plan.warnings?.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="note">No warnings on the final plan.</p>
        )}
      </section>
      {(plan.revision_history ?? []).length ? (
        <section>
          <h3>Revision history</h3>
          <ul>
            {plan.revision_history?.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

function MapPlan({ plan, labels }: { plan: Itinerary; labels: Record<string, Label> }) {
  const points = pointsFor(plan, labels);
  if (points.length < 2) return <p className="note">Not enough stored coordinates to plot this plan.</p>;
  const lats = points.map((point) => point.lat);
  const lngs = points.map((point) => point.lng);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  const spanLat = maxLat - minLat || 0.01;
  const spanLng = maxLng - minLng || 0.01;
  return (
    <div>
      <p className="note">Stored coordinates only. A tiled map is post-MVP.</p>
      <svg className="map" viewBox="0 0 320 200" role="img" aria-label="Place coordinates">
        {points.map((point) => {
          const x = 20 + ((point.lng - minLng) / spanLng) * 280;
          const y = 180 - ((point.lat - minLat) / spanLat) * 160;
          return (
            <g key={point.id}>
              <circle cx={x} cy={y} r="5" />
              <text x={x + 6} y={y + 4}>
                {point.name}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function pointsFor(plan: Itinerary, labels: Record<string, Label>) {
  const seen = new Set<string>();
  const points: { id: string; name: string; lat: number; lng: number }[] = [];
  const add = (id: string | null | undefined) => {
    if (!id || seen.has(id)) return;
    const label = labels[id];
    if (!label) return;
    seen.add(id);
    points.push({ id, name: label.name, lat: label.lat, lng: label.lng });
  };
  add(plan.stay?.id);
  for (const day of plan.days) {
    for (const slot of day.slots) add(slot.place_id);
  }
  return points;
}

function Badge({ provenance }: { provenance: string }) {
  if (provenance === "verified") return <span className="badge ok">✅ verified</span>;
  if (provenance === "api") return <span className="badge api">🌐 api</span>;
  return <span className="badge est">≈ estimated</span>;
}

function clock(value: string): string {
  return value.slice(0, 5);
}
