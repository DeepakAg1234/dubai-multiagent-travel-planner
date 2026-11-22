import Link from "next/link";

import { allCredits } from "@/lib/images";

export function Footer() {
  const credits = allCredits();
  return (
    <footer className="dj-footer">
      <div className="dj-wrap">
        <div className="dj-footer-top">
          <span className="dj-brand">Dubai Journey AI</span>
          <Link href="/plan" className="dj-btn dj-btn--sm">
            Plan My Trip
          </Link>
        </div>
        <p>
          Itineraries are planning aids built from a curated Dubai catalog. Prices are estimates unless marked
          verified, and nothing here is a booking or a live availability check. Already have a plan from another
          AI? <Link href="/audit">Check that plan</Link>.
        </p>
        <details>
          <summary>Photo credits ({credits.length})</summary>
          <p style={{ margin: "10px 0" }}>
            Photographs from Wikimedia Commons under the licenses shown. Map data &copy; OpenStreetMap contributors.
          </p>
          <ul>
            {credits.map((c) => (
              <li key={c.file}>
                <a href={c.source} target="_blank" rel="noreferrer">
                  {c.title.replace(/_/g, " ").replace(/\.[a-z]+$/i, "")}
                </a>{" "}
                &middot; {c.author} &middot; {c.license}
              </li>
            ))}
          </ul>
        </details>
      </div>
    </footer>
  );
}
