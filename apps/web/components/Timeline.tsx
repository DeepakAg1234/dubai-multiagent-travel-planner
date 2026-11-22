import type { TimelineRow } from "@/lib/types";

export function Timeline({ rows }: { rows: TimelineRow[] }) {
  return (
    <section className="card" aria-live="polite">
      <h2>Agents</h2>
      {rows.length === 0 ? <p className="note">Nodes appear here as the run streams.</p> : null}
      <div className="timeline">
        {rows.map((row) => (
          <article key={row.id} data-status={row.status}>
            <header>
              <span className="node">{row.node}</span>
              <span className="meta">
                {row.status}
                {row.durationMs != null ? ` · ${row.durationMs} ms` : ""}
              </span>
            </header>
            <p className="note">{row.summary}</p>
            {Object.keys(row.delta).length > 0 ? (
              <details>
                <summary>Output</summary>
                <pre>{JSON.stringify(row.delta, null, 2)}</pre>
              </details>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}
