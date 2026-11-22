import type { Snapshot } from "@/lib/types";

export function StateInspector({ snapshot }: { snapshot: Snapshot | null }) {
  if (!snapshot) return <p className="note">State slices show up after the first node finishes.</p>;
  const constraints = snapshot.constraints ?? {};
  const places = snapshot.candidates?.places ?? [];
  const restaurants = snapshot.candidates?.restaurants ?? [];
  return (
    <div className="stack">
      <dl>
        <dt>Days</dt>
        <dd>{String(constraints.days ?? "—")}</dd>
        <dt>Budget</dt>
        <dd>{constraints.budget_aed != null ? `AED ${String(constraints.budget_aed)}` : "—"}</dd>
        <dt>Hotel</dt>
        <dd>{String(constraints.hotel_tier ?? "—")}</dd>
        <dt>Start</dt>
        <dd>{String(constraints.start_date ?? "—")}</dd>
        <dt>Interests</dt>
        <dd>{Array.isArray(constraints.interests) ? constraints.interests.join(", ") : "—"}</dd>
        <dt>Revisions</dt>
        <dd>{snapshot.revision_count}</dd>
        <dt>Excluded</dt>
        <dd>{snapshot.excluded_ids.length ? snapshot.excluded_ids.join(", ") : "—"}</dd>
      </dl>
      <section>
        <h3>Candidates</h3>
        <p className="note">
          {places.length} places, {restaurants.length} restaurants
          {snapshot.candidates?.areas?.length ? ` in ${snapshot.candidates.areas.join(", ")}` : ""}.
        </p>
        <ul>
          {places.slice(0, 8).map((place) => (
            <li key={place.id}>
              {place.name} · {place.area}
              {place.operational_status && place.operational_status !== "open"
                ? ` · ${place.operational_status}`
                : ""}
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h3>Draft</h3>
        <p className="note">
          {snapshot.draft ? `${snapshot.draft.days.length} days` : "Not sequenced yet"}
          {snapshot.budget ? ` · AED ${snapshot.budget.total_aed}` : ""}
          {snapshot.budget ? (snapshot.budget.within_budget ? " · within budget" : " · over budget") : ""}
        </p>
      </section>
      {snapshot.holiday_notes.length ? (
        <section>
          <h3>Holiday notes</h3>
          <ul>
            {snapshot.holiday_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
