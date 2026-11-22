import type { RevisionFrame } from "@/lib/types";

export function RevisionDiff({ frames }: { frames: RevisionFrame[] }) {
  if (!frames.length) {
    return <p className="note">A revision loop lists the itinerary and budget before and after the change.</p>;
  }
  return (
    <div className="stack">
      {frames.map((frame, index) => (
        <article key={frame.id}>
          <h3>
            Loop {index + 1}
          </h3>
          <p>{frame.summary}</p>
          {frame.violations.length ? (
            <ul>
              {frame.violations.map((row) => (
                <li key={`${row.rule}-${row.detail}`}>
                  <strong>{row.severity}</strong> {row.rule}: {row.detail}
                </li>
              ))}
            </ul>
          ) : null}
          <div className="diff">
            <Slice title="Before" total={frame.before.total} themes={frame.before.themes} stay={frame.before.stay} />
            <Slice title="After" total={frame.after.total} themes={frame.after.themes} stay={frame.after.stay} />
          </div>
        </article>
      ))}
    </div>
  );
}

function Slice({
  title,
  total,
  themes,
  stay,
}: {
  title: string;
  total: number | null;
  themes: string[];
  stay: string | null;
}) {
  return (
    <section className="slice">
      <h3>{title}</h3>
      <p>{total == null ? "No budget yet" : `AED ${total}`}</p>
      <p className="note">{stay ?? "No stay"}</p>
      <ul>
        {themes.map((theme, index) => (
          <li key={`${theme}-${index}`}>{theme}</li>
        ))}
      </ul>
    </section>
  );
}
