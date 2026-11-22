const NODE_ID = /^[A-Za-z_][A-Za-z0-9_]*$/;

export function styleGraph(diagram: string, running: string[], finished: string[]): string {
  const source = diagram.trim();
  if (!source) return "";
  const lines = [source];
  const active = new Set(running.filter(isNode));
  for (const name of finished.filter(isNode)) {
    if (active.has(name)) continue;
    lines.push(`style ${name} fill:#f2f2f2,stroke:#222222,stroke-width:1px`);
  }
  for (const name of active) {
    lines.push(`style ${name} fill:#ffe1e7,stroke:#ff385c,stroke-width:2px`);
  }
  return lines.join("\n");
}

function isNode(name: string): boolean {
  return NODE_ID.test(name);
}
