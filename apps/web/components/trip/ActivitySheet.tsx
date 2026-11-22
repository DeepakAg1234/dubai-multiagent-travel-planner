"use client";

import { useEffect, useRef } from "react";

import { Close, Pin } from "@/components/site/Icons";
import { Photo } from "@/components/site/Photo";
import { altFor, photoForPlace } from "@/lib/images";
import { clock, duration, kindLabel, money, PROVENANCE, TRANSPORT_LABEL, type DayView, type Stop } from "@/lib/plan-view";

export function Provenance({ value }: { value: string }) {
  const info = PROVENANCE[value] ?? PROVENANCE.estimated;
  const cls = value === "verified" ? "dj-pill--ok" : value === "api" ? "dj-pill--teal" : "dj-pill--warn";
  return (
    <span className={`dj-pill ${cls}`} title={info.hint}>
      {info.label}
    </span>
  );
}

export function ActivitySheet({ stop, day, onClose }: { stop: Stop; day: DayView; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const photo = photoForPlace(stop.placeId, stop.category, stop.area);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const flagged = stop.status === "closed" || stop.status === "reopening";
  return (
    <div className="dj-sheet-bg" onClick={onClose} role="presentation">
      <div className="dj-sheet" role="dialog" aria-modal="true" aria-label={stop.name} onClick={(e) => e.stopPropagation()}>
        <button ref={closeRef} type="button" className="dj-sheet-close" aria-label="Close details" onClick={onClose}>
          <Close width={20} height={20} />
        </button>
        <Photo photo={photo} alt={altFor(photo, stop.name)} sizes="(max-width: 800px) 100vw, 760px" label={stop.name} />
        <div className="dj-sheet-body">
          <div>
            <span className="dj-eyebrow">
              Day {day.day} &middot; {kindLabel(stop.kind)}
            </span>
            <h2>{stop.name}</h2>
            {stop.area ? (
              <p className="dj-muted" style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6 }}>
                <Pin width={16} height={16} /> {stop.area}
                {stop.category ? ` \u00B7 ${stop.category.replace(/_/g, " ")}` : ""}
              </p>
            ) : null}
          </div>
          {flagged ? (
            <p className="dj-notice dj-notice--bad" role="status">
              This place is listed as <b>{stop.status}</b> in the planner&rsquo;s catalog. Check before you go.
            </p>
          ) : null}
          <div className="dj-facts">
            <div className="dj-fact">
              <small>Planned time</small>
              <b>
                {clock(stop.start)} &ndash; {clock(stop.end)}
              </b>
            </div>
            <div className="dj-fact">
              <small>Planned duration</small>
              <b>{duration(stop.minutes)}</b>
            </div>
            <div className="dj-fact">
              <small>Cost in this plan</small>
              {stop.cost ? (
                <>
                  <b>{stop.cost.total ? money(stop.cost.total) : "Free or included"}</b> <Provenance value={stop.cost.provenance} />
                </>
              ) : (
                <b>No separate cost listed</b>
              )}
            </div>
            <div className="dj-fact">
              <small>Getting here</small>
              {stop.legIn ? (
                <b>
                  {TRANSPORT_LABEL[stop.legIn.mode] ?? stop.legIn.mode}, {stop.legIn.minutes} min
                  {stop.legIn.distance_km ? ` (${stop.legIn.distance_km.toFixed(1)} km)` : ""}
                </b>
              ) : (
                <b>First stop or same area</b>
              )}
            </div>
          </div>
          {stop.legIn?.cost_aed != null ? (
            <p className="dj-muted" style={{ fontSize: 15 }}>
              Transport for this leg: {money(stop.legIn.cost_aed)} <Provenance value={stop.legIn.provenance} />
            </p>
          ) : null}
          <div className="dj-why">
            <b>Why it&rsquo;s in your plan.</b> It anchors &ldquo;{day.theme}&rdquo;
            {stop.notes ? `. Planner note: ${stop.notes}` : "."}
          </div>
          <p className="dj-muted" style={{ fontSize: 14 }}>
            Times and durations are planning estimates. Opening hours and ticket prices aren&rsquo;t verified here, so
            confirm them with the venue.
          </p>
        </div>
      </div>
    </div>
  );
}
