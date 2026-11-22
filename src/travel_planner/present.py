"""JSON and Markdown views of a planner run.

Exports are built in memory. Nothing here writes a file.
"""

from __future__ import annotations

from pydantic import BaseModel

from travel_planner.data.providers.attribution import OPEN_METEO_CC_BY, OSM_ODBL
from travel_planner.tools.catalog import CatalogTools

_USAGE_KEYS = ("calls", "prompt_tokens", "completion_tokens", "repairs", "fallbacks")
_DEGRADED_MARKERS = ("unavailable", "curated catalog", "straight-line")


def usage_delta(
    before: dict[str, dict[str, int]],
    after: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]]:
    """Per-node counts added between two ledger snapshots."""

    delta: dict[str, dict[str, int]] = {}
    for name in set(before) | set(after):
        start = before.get(name, {})
        end = after.get(name, {})
        row = {key: int(end.get(key, 0)) - int(start.get(key, 0)) for key in _USAGE_KEYS}
        if any(row.values()):
            delta[name] = row
    return delta


def present_state(
    values: dict[str, object],
    tools: CatalogTools,
    usage: dict[str, dict[str, int]],
) -> dict[str, object]:
    """Key TripState slices, plus labels so the UI can name slot ids."""

    draft = _dump(values.get("draft_itinerary"))
    final = _dump(values.get("final_itinerary"))
    warnings = _strings(values.get("warnings"))
    assumptions = _strings(values.get("assumptions"))
    holiday_notes = _holiday_notes(final or draft)
    texts = [*warnings, *assumptions, *_leg_sources(final or draft)]
    return {
        "constraints": _dump(values.get("constraints")),
        "assumptions": assumptions,
        "plan_brief": _dump(values.get("plan_brief")),
        "candidates": _candidates(values.get("candidates")),
        "stay_options": _dump(values.get("stay_options")) or [],
        "transport_options": _dump(values.get("transport_options")) or [],
        "draft": draft,
        "budget": _dump(values.get("budget_report")),
        "review": _dump(values.get("review_report")),
        "revision_count": int(values.get("revision_count") or 0),
        "excluded_ids": _strings(values.get("excluded_ids")),
        "warnings": warnings,
        "holiday_notes": holiday_notes,
        "final": final,
        "labels": _labels(tools),
        "degraded": any(marker in text for text in texts for marker in _DEGRADED_MARKERS),
        "attributions": _attributions(texts),
        "usage": usage,
    }


def result_payload(thread_id: str, snapshot: dict[str, object]) -> dict[str, object] | None:
    """Downloadable itinerary. None until a draft or final plan exists."""

    itinerary = snapshot.get("final") or snapshot.get("draft")
    if not isinstance(itinerary, dict):
        return None
    return {
        "thread_id": thread_id,
        "itinerary": itinerary,
        "labels": snapshot.get("labels") or {},
        "usage": snapshot.get("usage") or {},
        "degraded": bool(snapshot.get("degraded")),
        "attributions": snapshot.get("attributions") or [],
        "revision_count": snapshot.get("revision_count") or 0,
    }


def itinerary_markdown(payload: dict[str, object]) -> str:
    """Markdown for one itinerary payload. The caller sends it as the response."""

    itinerary = payload["itinerary"]
    assert isinstance(itinerary, dict)
    labels = payload.get("labels") if isinstance(payload.get("labels"), dict) else {}
    lines = ["# Dubai itinerary", ""]
    narrative = str(itinerary.get("narrative") or "").strip()
    if narrative:
        lines.extend([narrative, ""])
    stay = itinerary.get("stay") if isinstance(itinerary.get("stay"), dict) else None
    if stay:
        lines.append(
            f"Stay: {stay.get('name')} ({stay.get('area')}, {stay.get('tier')}, "
            f"{stay.get('season')})."
        )
        lines.append("")
    for day in itinerary.get("days") or []:
        if not isinstance(day, dict):
            continue
        lines.append(f"## Day {day.get('day')} — {day.get('theme')}")
        lines.append("")
        note = day.get("holiday_note")
        if note:
            lines.append(f"Holiday: {note}")
            lines.append("")
        for slot in day.get("slots") or []:
            if not isinstance(slot, dict):
                continue
            name = _slot_name(slot, labels)
            start = _clock(slot.get("start"))
            end = _clock(slot.get("end"))
            extra = f" — {slot.get('notes')}" if slot.get("notes") else ""
            status = _status(slot.get("place_id"), labels)
            flag = f" [{status}]" if status else ""
            lines.append(f"- {start}–{end} {slot.get('kind')}: {name}{extra}{flag}")
        for leg in day.get("legs") or []:
            if not isinstance(leg, dict):
                continue
            cost = leg.get("cost_aed")
            cost_text = "n/a" if cost is None else f"AED {cost:g}"
            lines.append(
                f"- Leg {leg.get('mode')} {leg.get('minutes')} min, {cost_text}, "
                f"{_provenance_word(str(leg.get('provenance') or 'estimated'))}"
            )
        lines.append("")
    budget = itinerary.get("budget") if isinstance(itinerary.get("budget"), dict) else None
    if budget:
        lines.extend(["## Budget", ""])
        lines.append("| Category | Item | Total (AED) | Provenance |")
        lines.append("| --- | --- | ---: | --- |")
        for line in budget.get("lines") or []:
            if not isinstance(line, dict):
                continue
            lines.append(
                f"| {line.get('category')} | {line.get('item')} | {line.get('total_aed')} | "
                f"{_provenance_word(str(line.get('provenance') or 'estimated'))} |"
            )
        lines.append("")
        lines.append(f"Total: AED {budget.get('total_aed')}")
        cap = budget.get("budget_aed")
        if cap is not None:
            lines.append(f"Budget: AED {cap}")
        lines.append("")
    assumptions = itinerary.get("assumptions") or []
    if assumptions:
        lines.extend(["## Assumptions", ""])
        lines.extend(f"- {item}" for item in assumptions)
        lines.append("")
    warnings = itinerary.get("warnings") or []
    if warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {item}" for item in warnings)
        lines.append("")
    history = itinerary.get("revision_history") or []
    if history:
        lines.extend(["## Revisions", ""])
        lines.extend(f"- {item}" for item in history)
        lines.append("")
    attributions = payload.get("attributions") or []
    if attributions:
        lines.extend(["## Sources", ""])
        lines.extend(f"- {item}" for item in attributions)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _dump(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_dump(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _dump(item) for key, item in value.items()}
    return value


def _candidates(value: object) -> dict[str, object] | None:
    dumped = _dump(value)
    if not isinstance(dumped, dict):
        return None
    places = []
    for row in dumped.get("places") or []:
        if isinstance(row, dict):
            places.append(
                _pick(
                    row,
                    ("id", "name", "area", "category", "operational_status", "tags"),
                )
            )
    restaurants = []
    for row in dumped.get("restaurants") or []:
        if isinstance(row, dict):
            restaurants.append(_pick(row, ("id", "name", "area", "price_band", "meal_types")))
    return {"places": places, "restaurants": restaurants, "areas": dumped.get("areas") or []}


def _pick(row: dict[str, object], keys: tuple[str, ...]) -> dict[str, object]:
    return {key: row.get(key) for key in keys}


def _labels(tools: CatalogTools) -> dict[str, dict[str, object]]:
    labels: dict[str, dict[str, object]] = {}
    for place in tools.places:
        labels[place.id] = {
            "name": place.name,
            "area": place.area,
            "lat": place.lat,
            "lng": place.lng,
            "kind": "place",
            "category": place.category,
            "operational_status": place.operational_status,
        }
    for restaurant in tools.restaurants:
        labels[restaurant.id] = {
            "name": restaurant.name,
            "area": restaurant.area,
            "lat": restaurant.lat,
            "lng": restaurant.lng,
            "kind": "restaurant",
            "category": restaurant.price_band,
            "operational_status": "open",
        }
    for hotel in tools.hotels:
        labels[hotel.id] = {
            "name": hotel.name,
            "area": hotel.area,
            "lat": hotel.lat,
            "lng": hotel.lng,
            "kind": "hotel",
            "category": hotel.tier,
            "operational_status": "open",
        }
    return labels


def _holiday_notes(itinerary: object) -> list[str]:
    if not isinstance(itinerary, dict):
        return []
    notes: list[str] = []
    for day in itinerary.get("days") or []:
        if isinstance(day, dict) and day.get("holiday_note"):
            notes.append(f"Day {day.get('day')}: {day['holiday_note']}")
    return notes


def _leg_sources(itinerary: object) -> list[str]:
    if not isinstance(itinerary, dict):
        return []
    sources: list[str] = []
    for day in itinerary.get("days") or []:
        if not isinstance(day, dict):
            continue
        for leg in day.get("legs") or []:
            if isinstance(leg, dict) and leg.get("source"):
                sources.append(str(leg["source"]))
    return sources


def _attributions(texts: list[str]) -> list[str]:
    found: list[str] = []
    blob = "\n".join(texts)
    if "ODbL" in blob or "OpenStreetMap" in blob:
        found.append(OSM_ODBL)
    if "Open-Meteo" in blob or "CC BY" in blob:
        found.append(OPEN_METEO_CC_BY)
    return found


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _slot_name(slot: dict[str, object], labels: dict[str, object]) -> str:
    place_id = slot.get("place_id")
    if not isinstance(place_id, str) or not place_id:
        return str(slot.get("kind") or "slot")
    label = labels.get(place_id)
    if isinstance(label, dict) and label.get("name"):
        return str(label["name"])
    return place_id


def _status(place_id: object, labels: dict[str, object]) -> str:
    if not isinstance(place_id, str):
        return ""
    label = labels.get(place_id)
    if not isinstance(label, dict):
        return ""
    status = str(label.get("operational_status") or "")
    if status in {"closed", "reopening"}:
        return status
    return ""


def _clock(value: object) -> str:
    text = str(value or "")
    return text[:5] if len(text) >= 5 else text


def _provenance_word(provenance: str) -> str:
    if provenance == "verified":
        return "verified"
    if provenance == "api":
        return "api"
    return "estimated"
