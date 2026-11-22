import type { Metadata } from "next";

import { TripView } from "@/components/trip/TripView";

export const metadata: Metadata = { title: "Your Dubai itinerary | Dubai Journey AI" };

export default function TripPage() {
  return <TripView />;
}
