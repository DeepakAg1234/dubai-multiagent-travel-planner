"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Close, Menu, Plane } from "./Icons";

const LINKS = [
  { href: "/#explore", label: "Explore Dubai" },
  { href: "/#how", label: "How It Works" },
  { href: "/audit", label: "Check a Plan" },
  { href: "/#sample", label: "Sample Itinerary" },
];

/** `over` sits transparently on a hero photograph until the page scrolls. */
export function SiteNav({ over = false }: { over?: boolean }) {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const solid = !over || scrolled;
  return (
    <>
      <header className={`dj-nav ${solid ? "dj-nav--solid" : "dj-nav--over"}`}>
        <div className="dj-wrap dj-nav-in">
          <Link href="/" className="dj-brand" aria-label="Dubai Journey AI, home">
            <span className="dj-brand-mark" aria-hidden="true">
              <Plane style={{ color: "#fff" }} />
            </span>
            Dubai Journey AI
          </Link>
          <nav className="dj-links" aria-label="Primary">
            {LINKS.map((link) => (
              <Link key={link.href} href={link.href}>
                {link.label}
              </Link>
            ))}
          </nav>
          <Link href="/plan" className="dj-btn dj-btn--sm dj-nav-cta">
            Plan My Trip
          </Link>
          <button
            type="button"
            className="dj-burger"
            aria-label="Open menu"
            aria-expanded={open}
            onClick={() => setOpen(true)}
          >
            <Menu width={24} height={24} />
          </button>
        </div>
      </header>
      <div className={`dj-drawer ${open ? "is-open" : ""}`} onClick={() => setOpen(false)} role="presentation">
        <div className="dj-drawer-panel" role="dialog" aria-modal="true" aria-label="Menu" onClick={(e) => e.stopPropagation()}>
          <button type="button" className="dj-burger" style={{ display: "inline-flex", justifySelf: "end" }} aria-label="Close menu" onClick={() => setOpen(false)}>
            <Close width={22} height={22} />
          </button>
          {LINKS.map((link) => (
            <Link key={link.href} href={link.href} onClick={() => setOpen(false)}>
              {link.label}
            </Link>
          ))}
          <Link href="/plan" className="dj-btn" style={{ marginTop: 16 }} onClick={() => setOpen(false)}>
            Plan My Trip
          </Link>
        </div>
      </div>
    </>
  );
}
