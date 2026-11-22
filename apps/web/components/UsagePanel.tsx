import type { LlmMeta, UsageRow } from "@/lib/types";

type Props = {
  llm: LlmMeta | null;
  usage: Record<string, UsageRow>;
  budget: number;
  degraded: boolean;
  attributions: string[];
};

export function UsagePanel({ llm, usage, budget, degraded, attributions }: Props) {
  const rows = Object.entries(usage);
  const calls = rows.reduce((sum, [, row]) => sum + row.calls, 0);
  const tokens = rows.reduce((sum, [, row]) => sum + row.prompt_tokens + row.completion_tokens, 0);
  return (
    <section className="card">
      <h2>Usage</h2>
      <p className="note">
        {llm
          ? `${llm.default_provider} / ${llm.default_model} for planning${llm.default_enabled ? "" : " (stubbed)"}. ${llm.review_provider} / ${llm.review_model} for review${llm.review_enabled ? "" : " (stubbed)"}.`
          : "Provider status arrives with the run."}
      </p>
      <p className="note">
        This run: {calls} model calls, {tokens} tokens. Live HTTP calls are capped at {budget} per run.
        Account free-tier ceilings stay on the Groq and Ollama dashboards.
      </p>
      {degraded ? <p className="degraded">Live routing or weather fell back to the curated catalog.</p> : null}
      {rows.length ? (
        <table className="usage">
          <thead>
            <tr>
              <th>Node</th>
              <th>Calls</th>
              <th>Tokens</th>
              <th>Repairs</th>
              <th>Fallbacks</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([node, row]) => (
              <tr key={node}>
                <td>{node.replaceAll("_", "_​")}</td>
                <td>{row.calls}</td>
                <td>{row.prompt_tokens + row.completion_tokens}</td>
                <td>{row.repairs}</td>
                <td>{row.fallbacks}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="note">No model calls yet. Missing keys keep the deterministic stubs, so this table stays empty.</p>
      )}
      {attributions.length ? (
        <ul>
          {attributions.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
