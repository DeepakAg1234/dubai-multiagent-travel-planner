import type { Metadata } from "next";

import "../globals.css";

export const metadata: Metadata = {
  title: "Developer view | Dubai planner",
  robots: { index: false, follow: false },
};

export default function DevLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
