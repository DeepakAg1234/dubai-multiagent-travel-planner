import type { Metadata } from "next";

import { AuditStudio } from "@/components/audit/AuditStudio";
import { Footer } from "@/components/site/Footer";
import { SiteNav } from "@/components/site/SiteNav";

export const metadata: Metadata = {
  title: "Check a Dubai plan | Dubai Journey AI",
  description:
    "Paste a Dubai itinerary from ChatGPT or Claude. We check the places, the hours, the travel time, and the budget, then show a practical version.",
};

export default function AuditPage() {
  return (
    <>
      <SiteNav />
      <main id="main">
        <AuditStudio />
      </main>
      <Footer />
    </>
  );
}
