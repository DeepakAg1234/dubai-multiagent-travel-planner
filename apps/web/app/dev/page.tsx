import { notFound } from "next/navigation";

import { PlannerApp } from "@/components/PlannerApp";

/**
 * Agent graph, state, revisions, token usage and diagnostics. Not linked from the consumer
 * site. Available in development, or in production only when ENABLE_DEV_VIEW=1.
 */
export default function DevPage() {
  if (process.env.NODE_ENV === "production" && process.env.ENABLE_DEV_VIEW !== "1") notFound();
  return (
    <main>
      <PlannerApp />
    </main>
  );
}
