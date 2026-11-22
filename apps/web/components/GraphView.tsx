"use client";

import { useEffect, useMemo, useState } from "react";

import { styleGraph } from "@/lib/graph-style";

type Props = {
  diagram: string;
  running: string[];
  finished: string[];
};

export function GraphView({ diagram, running, finished }: Props) {
  const styled = useMemo(() => styleGraph(diagram, running, finished), [diagram, running, finished]);
  const [svg, setSvg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!styled) return;
    let cancelled = false;
    const render = async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, securityLevel: "loose", fontFamily: "inherit" });
        const id = `planner-${Math.random().toString(36).slice(2)}`;
        const drawn = await mermaid.render(id, styled);
        if (!cancelled) {
          setSvg(drawn.svg);
          setError("");
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "The graph could not be drawn.");
      }
    };
    void render();
    return () => {
      cancelled = true;
    };
  }, [styled]);

  if (!diagram) {
    return <p className="note">The graph loads from the planner API. Start the API if this stays empty.</p>;
  }
  if (error) {
    return (
      <>
        <p className="note">{error}</p>
        <pre>{styled}</pre>
      </>
    );
  }
  if (!svg) return <p className="note">Drawing the graph…</p>;
  return <div aria-label="Planner graph" dangerouslySetInnerHTML={{ __html: svg }} />;
}
