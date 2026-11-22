import type { Metadata } from "next";
import { Suspense } from "react";

import { PlanWizard } from "@/components/plan/PlanWizard";

export const metadata: Metadata = { title: "Plan My Trip | Dubai Journey AI" };

export default function PlanPage() {
  return (
    <main id="main">
      <Suspense fallback={<div className="dj-center">Loading&hellip;</div>}>
        <PlanWizard />
      </Suspense>
    </main>
  );
}
