"use client";

import "leaflet/dist/leaflet.css";

import type { Map as LeafletMap, Marker } from "leaflet";
import { useEffect, useRef } from "react";

import type { Stop } from "@/lib/plan-view";

type Props = {
  stops: Stop[];
  selected: string | null;
  onSelect: (key: string) => void;
  /** Re-fit when the day changes. */
  dayKey: number;
};

/**
 * Leaflet map with OpenStreetMap tiles. Markers are the day's numbered stops and are joined in
 * visiting order with straight lines. They are not road routes.
 */
export default function ItineraryMap({ stops, selected, onSelect, dayKey }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<LeafletMap | null>(null);
  const markers = useRef<Map<string, Marker>>(new Map());
  const layer = useRef<import("leaflet").LayerGroup | null>(null);
  const lib = useRef<typeof import("leaflet") | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    let cancelled = false;
    void import("leaflet").then((L) => {
      if (cancelled || !host.current || map.current) return;
      lib.current = L;
      map.current = L.map(host.current, { scrollWheelZoom: false, zoomControl: true }).setView([25.2048, 55.2708], 11);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map.current);
      layer.current = L.layerGroup().addTo(map.current);
      draw();
      // The map can start hidden (collapsed on small screens); re-measure when it appears.
      observer = new ResizeObserver(() => {
        map.current?.invalidateSize();
        if (host.current && host.current.clientHeight > 0) draw();
      });
      observer.observe(host.current);
    });
    let observer: ResizeObserver | undefined;
    const markerStore = markers.current;
    return () => {
      cancelled = true;
      observer?.disconnect();
      map.current?.remove();
      map.current = null;
      markerStore.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function draw() {
    const L = lib.current;
    const m = map.current;
    const group = layer.current;
    if (!L || !m || !group) return;
    group.clearLayers();
    markers.current.clear();
    const points: [number, number][] = [];
    for (const stop of stops) {
      if (stop.lat === null || stop.lng === null || stop.n === null) continue;
      const point: [number, number] = [stop.lat, stop.lng];
      points.push(point);
      const icon = L.divIcon({
        className: "",
        html: `<div class="dj-pin${stop.key === selected ? " is-sel" : ""}">${stop.n}</div>`,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      });
      const marker = L.marker(point, { icon, title: `${stop.n}. ${stop.name}`, keyboard: true, alt: `Stop ${stop.n}: ${stop.name}` });
      marker.bindTooltip(`${stop.n}. ${stop.name}`, { direction: "top", offset: [0, -14] });
      marker.on("click", () => onSelectRef.current(stop.key));
      marker.addTo(group);
      markers.current.set(stop.key, marker);
    }
    if (points.length > 1) L.polyline(points, { color: "#147d83", weight: 3, opacity: 0.7, dashArray: "6 8" }).addTo(group);
    if (points.length) m.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 15 });
  }

  // Redraw when the day or its stops change.
  useEffect(() => {
    draw();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dayKey, stops]);

  // Highlight the selected stop without refitting the map.
  useEffect(() => {
    markers.current.forEach((marker, key) => {
      const el = marker.getElement()?.querySelector(".dj-pin");
      el?.classList.toggle("is-sel", key === selected);
    });
    const marker = selected ? markers.current.get(selected) : null;
    if (marker && map.current) map.current.panTo(marker.getLatLng(), { animate: true });
  }, [selected]);

  return <div ref={host} className="dj-map" role="region" aria-label="Map of today's stops" />;
}
