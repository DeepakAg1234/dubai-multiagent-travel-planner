import type { Metadata, Viewport } from "next";
import { DM_Sans, Inter, Playfair_Display } from "next/font/google";

import "./journey.css";

const display = Playfair_Display({ subsets: ["latin"], variable: "--font-display", display: "swap" });
const body = DM_Sans({ subsets: ["latin"], variable: "--font-body", display: "swap" });
// The developer dashboard under /dev still uses Inter.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: "Dubai Journey AI | Your Dubai. Your Way.",
  description:
    "A personalized Dubai itinerary, plus a check for plans written by ChatGPT or Claude: real places, workable days, and a budget that adds up.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#14283f",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${inter.variable}`}>
      <body>{children}</body>
    </html>
  );
}
