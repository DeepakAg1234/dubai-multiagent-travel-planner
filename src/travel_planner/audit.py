"""Check a pasted itinerary against the Dubai catalog and the planning rules.

A chatbot can write a confident plan. This module does not. It matches names
to the curated catalog, prices and routes only those matches, and runs the
same budget and review rules as the planner. A repair keeps the places that
are actually usable and rebuilds the days. No live booking API is called.
"""

from __future__ import annotations

import re
from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field

from travel_planner.data.areas import stay_area
from travel_planner.graph.shortlist import meals_for_places
from travel_planner.models import (
    BudgetReport,
    ClimateMonth,
    Constraints,
    DayPlan,
    Fare,
    Holiday,
    Hotel,
    Itinerary,
    Leg,
    Place,
    PriceBand,
    Restaurant,
    ReviewReport,
    Slot,
    StayOption,
    TransitEdge,
    TransitStation,
)
from travel_planner.rules.budget import compute_budget, midpoint, season_for
from travel_planner.rules.fares import TransitGraph, route_leg
from travel_planner.rules.hours import add_minutes
from travel_planner.rules.review import run_rules
from travel_planner.rules.sequencing import sequence_itinerary

EXAMPLE_TEXT = """\
2-day Dubai trip starting 2026-03-19.
Budget AED 900. Avoid crowded places.
Stay at Atlantis The Palm.

Day 1
Morning: Museum of the Future
Then Dubai Chocolate Factory
Afternoon: Dubai Museum
Evening: Jumeirah Public Beach

Day 2
Morning: Burj Khalifa At the Top
Afternoon: The Dubai Mall
Evening: Dubai Crystal Caves
"""

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_DAY_HEADER = re.compile(r"(?im)^\s*day\s+(\d+)\b")
_META = re.compile(
    r"\b(budget|aed|dirham|starting|starts|start date|avoid|crowd|adults?|"
    r"travell?ers?|stay at|nights?|per person|flexible)\b",
    re.IGNORECASE,
)
_STOP = frozenset(
    {
        "morning",
        "afternoon",
        "evening",
        "night",
        "then",
        "next",
        "visit",
        "at",
        "the",
        "a",
        "an",
        "and",
        "or",
        "with",
        "for",
        "to",
        "from",
        "day",
        "lunch",
        "dinner",
        "breakfast",
        "nearby",
        "around",
        "stroll",
        "walk",
        "explore",
        "see",
        "go",
        "optional",
        "free",
        "time",
        "later",
        "after",
        "before",
    }
)
_TITLES = {
    "budget_compliance": "The cost does not fit the budget",
    "operational_status": "A place is not open",
    "day_length": "A day is the wrong length",
    "travel": "Travel between stops is too long",
    "opening_hours": "A stop falls outside opening hours",
    "duplicates": "The same stop is repeated",
    "completeness": "A practical piece is missing",
    "crowds": "A stop is likely to be crowded",
    "interest_coverage": "An interest is not covered",
    "provenance": "A price is missing its source",
    "not_in_catalog": "We could not find this place",
}

Verdict = Literal["clear", "repaired", "still_blocked"]
Kind = Literal["place", "restaurant", "hotel"]


class AuditFinding(BaseModel):
    code: str
    severity: Literal["blocker", "warning"]
    title: str
    detail: str


class RecognizedStop(BaseModel):
    name: str
    kind: Kind
    area: str
    day: int | None = None
    status: str | None = None


class AuditReport(BaseModel):
    verdict: Verdict
    headline: str
    summary: str
    assumptions: list[str] = Field(default_factory=list)
    repairs: list[str] = Field(default_factory=list)
    recognized: list[RecognizedStop] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)
    findings: list[AuditFinding] = Field(default_factory=list)
    remaining: list[AuditFinding] = Field(default_factory=list)
    original: Itinerary | None = None
    repaired: Itinerary | None = None
    labels: dict[str, dict[str, object]] = Field(default_factory=dict)


class _Hit:
    def __init__(self, kind: Kind, row: Place | Restaurant | Hotel, day: int | None) -> None:
        self.kind = kind
        self.row = row
        self.day = day

    @property
    def id(self) -> str:
        return self.row.id

    @property
    def name(self) -> str:
        return self.row.name


def audit_itinerary(
    text: str,
    *,
    places: list[Place],
    restaurants: list[Restaurant],
    hotels: list[Hotel],
    stations: list[TransitStation],
    edges: list[TransitEdge],
    fares: list[Fare],
    bands: list[PriceBand],
    holidays: list[Holiday],
    climate: list[ClimateMonth],
    buffer_pct: float = 10.0,
) -> AuditReport:
    """Return a verdict, the problems in the pasted plan, and a repaired plan."""

    raw = text.strip()
    constraints = _constraints(raw)
    hits, unknown = _match(raw, places, restaurants, hotels, constraints.days)
    graph = TransitGraph(stations, edges)
    place_by_id = {row.id: row for row in places}
    restaurant_by_id = {row.id: row for row in restaurants}
    names = {row.id: row.name for row in (*places, *restaurants, *hotels)}

    stay = _first_hotel(hits, constraints, hotels)
    original = _schedule_pasted(hits, constraints, stay, graph, fares)
    original_budget = _price(
        original,
        constraints,
        place_by_id,
        restaurant_by_id,
        hotels,
        bands,
        fares,
        buffer_pct,
        holidays,
        graph,
    )
    original.budget = original_budget
    original_review = _review(
        constraints, original, original_budget, place_by_id, restaurant_by_id, holidays
    )
    findings = _unknown_findings(unknown) + _from_review(original_review, names)

    repaired, repairs, remaining_review = _repair(
        hits,
        unknown,
        constraints,
        stay,
        hotels,
        restaurants,
        stations,
        edges,
        fares,
        bands,
        holidays,
        climate,
        buffer_pct,
        place_by_id,
        restaurant_by_id,
        names,
        graph,
    )
    verdict, headline, summary = _story(
        findings,
        unknown,
        original_review.passed,
        remaining_review.passed if remaining_review is not None else False,
        repaired is not None,
    )
    return AuditReport(
        verdict=verdict,
        headline=headline,
        summary=summary,
        assumptions=_assumptions(constraints, stay, unknown),
        repairs=repairs,
        recognized=[_recognized(hit) for hit in hits],
        unknown=unknown,
        findings=findings,
        remaining=_from_review(remaining_review, names) if remaining_review else [],
        original=original,
        repaired=repaired,
        labels=_labels(places, restaurants, hotels),
    )


def _constraints(text: str) -> Constraints:
    days = _days(text)
    budget = _budget(text)
    start = _start_date(text)
    avoid = bool(re.search(r"avoid\s+crowd|not\s+crowded|fewer\s+crowd", text, re.I))
    tier = None
    if re.search(r"\bluxury hotel\b|\bfive[- ]star\b|\b5[- ]star\b", text, re.I):
        tier = "luxury"
    elif re.search(r"\bmid[- ]range hotel\b", text, re.I):
        tier = "mid"
    elif re.search(r"\b(budget|affordable|cheap)\s+hotel\b", text, re.I):
        tier = "budget"
    travelers = 1
    found = re.search(r"\b(\d+)\s+(?:adults?|people|travell?ers?)\b", text, re.I)
    if found:
        travelers = min(12, max(1, int(found.group(1))))
    elif re.search(r"\bcouple\b", text, re.I):
        travelers = 2
    return Constraints(
        days=days,
        budget_aed=budget,
        travelers=travelers,
        hotel_tier=tier,
        avoid_crowds=avoid,
        start_date=start,
    )


def _days(text: str) -> int:
    headers = [int(value) for value in _DAY_HEADER.findall(text)]
    stated = re.search(r"\b(\d+)\s*[- ]?\s*days?\b", text, re.I)
    count = max(headers) if headers else 1
    if stated:
        count = max(count, int(stated.group(1)))
    return min(7, max(1, count))


def _budget(text: str) -> float | None:
    near = re.search(
        r"budget[^\d]{0,24}(?:aed|dirhams?)?\s*([\d,]+(?:\.\d+)?)",
        text,
        re.I,
    )
    if near is None:
        near = re.search(r"(?:aed|dirhams?)\s*([\d,]+(?:\.\d+)?)", text, re.I)
    if near is None:
        return None
    return float(near.group(1).replace(",", ""))


def _start_date(text: str) -> date | None:
    iso = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text)
    if iso:
        return _safe_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    written = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
        r"(january|february|march|april|may|june|july|august|september|"
        r"october|november|december)\s+(20\d{2})\b",
        text,
        re.I,
    )
    if written is None:
        return None
    month = _MONTHS[written.group(2).lower()]
    return _safe_date(int(written.group(3)), month, int(written.group(1)))


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _match(
    text: str,
    places: list[Place],
    restaurants: list[Restaurant],
    hotels: list[Hotel],
    days: int,
) -> tuple[list[_Hit], list[str]]:
    index: list[tuple[str, Kind, Place | Restaurant | Hotel]] = []
    catalog: list[tuple[Kind, Place | Restaurant | Hotel]] = [
        *[("place", row) for row in places],
        *[("restaurant", row) for row in restaurants],
        *[("hotel", row) for row in hotels],
    ]
    for kind, row in catalog:
        phrase = _norm(row.name)
        if len(phrase) < 4:
            continue
        index.append((phrase, kind, row))
        if phrase.startswith("the "):
            short = phrase[4:]
            if len(short) >= 4:
                index.append((short, kind, row))
    index.sort(key=lambda item: len(item[0]), reverse=True)

    hits: list[_Hit] = []
    unknown: list[str] = []
    seen: set[tuple[str, int | None]] = set()
    day = 1
    for line in text.splitlines():
        header = _DAY_HEADER.search(line)
        if header:
            day = min(days, max(1, int(header.group(1))))
        normalized = _norm(line)
        if not normalized:
            continue
        spans: list[tuple[int, int]] = []
        for phrase, kind, row in index:
            found = re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", normalized)
            if found is None or _overlaps(spans, found.start(), found.end()):
                continue
            spans.append((found.start(), found.end()))
            slot_day = None if kind == "hotel" else day
            key = (row.id, slot_day)
            if key in seen:
                continue
            seen.add(key)
            hits.append(_Hit(kind, row, slot_day))
        leftover = _leftover(normalized, spans)
        if leftover and not _META.search(line):
            unknown.append(leftover)
    return hits, _unique(unknown)


def _overlaps(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(start < right and end > left for left, right in spans)


def _leftover(normalized: str, spans: list[tuple[int, int]]) -> str | None:
    if not spans:
        tokens = [token for token in normalized.split() if token not in _STOP and len(token) > 1]
        if len(tokens) < 2:
            return None
        return " ".join(tokens).title()
    chars = list(normalized)
    for start, end in spans:
        for index in range(start, end):
            chars[index] = " "
    tokens = [token for token in "".join(chars).split() if token not in _STOP and len(token) > 1]
    if len(tokens) < 2:
        return None
    return " ".join(tokens).title()


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(value)
    return ordered


def _first_hotel(hits: list[_Hit], constraints: Constraints, hotels: list[Hotel]) -> StayOption:
    for hit in hits:
        if hit.kind == "hotel" and isinstance(hit.row, Hotel):
            return hit.row.stay_option(season_for(constraints.start_date))
    area = "Downtown"
    for hit in hits:
        if hit.kind == "place" and isinstance(hit.row, Place):
            area = stay_area(hit.row.area)
            break
    return _cheapest(hotels, constraints, area).stay_option(season_for(constraints.start_date))


def _cheapest(hotels: list[Hotel], constraints: Constraints, area: str | None) -> Hotel:
    season = season_for(constraints.start_date)
    tier = constraints.hotel_tier
    pool = [hotel for hotel in hotels if tier is None or hotel.tier == tier]
    if area is not None:
        local = [hotel for hotel in pool if hotel.area == area]
        if local:
            pool = local
    if not pool:
        pool = list(hotels)

    def nightly(hotel: Hotel) -> float:
        stay = hotel.stay_option(season)
        return midpoint(stay.nightly_min_aed, stay.nightly_max_aed)

    return min(pool, key=nightly)


def _schedule_pasted(
    hits: list[_Hit],
    constraints: Constraints,
    stay: StayOption,
    graph: TransitGraph,
    fares: list[Fare],
) -> Itinerary:
    grouped: dict[int, list[_Hit]] = {day: [] for day in range(1, constraints.days + 1)}
    for hit in hits:
        if hit.kind == "hotel" or hit.day is None:
            continue
        grouped.setdefault(hit.day, []).append(hit)
    days: list[DayPlan] = []
    for number in range(1, constraints.days + 1):
        slots, legs = _lay_out(grouped.get(number, []), graph, fares)
        theme = "As pasted" if slots else "Nothing on this day matched our Dubai list"
        days.append(DayPlan(day=number, theme=theme, slots=slots, legs=legs))
    return Itinerary(
        days=days,
        stay=stay,
        assumptions=["Times are filled in when the pasted plan does not name a clock time."],
    )


def _lay_out(
    hits: list[_Hit],
    graph: TransitGraph,
    fares: list[Fare],
) -> tuple[list[Slot], list[Leg]]:
    slots: list[Slot] = []
    legs: list[Leg] = []
    cursor = time(9, 0)
    previous: Place | None = None
    for hit in hits[:12]:
        current = _as_place(hit)
        if previous is not None:
            leg = route_leg(previous, current, graph, fares, when=cursor)
            legs.append(leg)
            cursor = _later(cursor, leg.minutes)
        minutes = 75 if hit.kind == "restaurant" else _visit_minutes(hit)
        start = cursor
        end = _later(start, minutes)
        notes = None
        kind: Literal["activity", "meal"] = "activity"
        if hit.kind == "restaurant":
            kind = "meal"
            notes = "lunch" if start < time(16, 0) else "dinner"
        slots.append(
            Slot(start=start, end=end, place_id=hit.id, kind=kind, notes=notes)
        )
        cursor = end
        previous = current
    return slots, legs


def _visit_minutes(hit: _Hit) -> int:
    if isinstance(hit.row, Place) and hit.row.typical_visit_minutes:
        return hit.row.typical_visit_minutes
    return 60


def _as_place(hit: _Hit) -> Place:
    row = hit.row
    if isinstance(row, Place):
        return row
    return Place(
        provenance=row.provenance,
        source=row.source,
        as_of=row.as_of,
        id=row.id,
        name=row.name,
        category="restaurant" if hit.kind == "restaurant" else "hotel",
        area=row.area,
        lat=row.lat,
        lng=row.lng,
    )


def _later(when: time, minutes: int) -> time:
    total = when.hour * 60 + when.minute + minutes
    if total >= 24 * 60 - 1:
        return time(23, 59)
    return add_minutes(when, minutes)


def _price(
    itinerary: Itinerary,
    constraints: Constraints,
    places: dict[str, Place],
    restaurants: dict[str, Restaurant],
    hotels: list[Hotel],
    bands: list[PriceBand],
    fares: list[Fare],
    buffer_pct: float,
    holidays: list[Holiday],
    graph: TransitGraph,
) -> BudgetReport:
    dropped = 0
    if constraints.start_date is not None:
        window = [
            holiday
            for holiday in holidays
            if holiday.start <= constraints.start_date <= holiday.end
        ]
        dropped = sum(1 for holiday in window if "drop_lunch" in holiday.effects)
    return compute_budget(
        itinerary,
        constraints,
        places=places,
        restaurants=restaurants,
        hotels=hotels,
        bands=bands,
        fares=fares,
        buffer_pct=buffer_pct,
        drop_lunch_days=dropped,
        graph=graph,
    )


def _review(
    constraints: Constraints,
    itinerary: Itinerary,
    budget: BudgetReport,
    places: dict[str, Place],
    restaurants: dict[str, Restaurant],
    holidays: list[Holiday],
) -> ReviewReport:
    return run_rules(
        {
            "constraints": constraints,
            "draft_itinerary": itinerary,
            "budget_report": budget,
        },
        places=places,
        restaurants=restaurants,
        holidays=holidays,
    )


def _repair(
    hits: list[_Hit],
    unknown: list[str],
    constraints: Constraints,
    stay: StayOption,
    hotels: list[Hotel],
    restaurants: list[Restaurant],
    stations: list[TransitStation],
    edges: list[TransitEdge],
    fares: list[Fare],
    bands: list[PriceBand],
    holidays: list[Holiday],
    climate: list[ClimateMonth],
    buffer_pct: float,
    places: dict[str, Place],
    restaurant_by_id: dict[str, Restaurant],
    names: dict[str, str],
    graph: TransitGraph,
) -> tuple[Itinerary | None, list[str], ReviewReport | None]:
    _ = names
    open_places = _open_places(hits)
    notes: list[str] = []
    if unknown:
        count = len(unknown)
        label = "stop" if count == 1 else "stops"
        notes.append(f"Left out {count} {label} we could not find in Dubai.")
    closed = [
        hit.name
        for hit in hits
        if hit.kind == "place"
        and isinstance(hit.row, Place)
        and hit.row.operational_status != "open"
    ]
    closed_names = _unique(closed)
    if closed_names:
        verb = "it is" if len(closed_names) == 1 else "they are"
        notes.append(f"Removed {', '.join(closed_names)} because {verb} not open.")
    if not open_places:
        notes.append("No open place from the pasted plan was left to rebuild.")
        return None, notes, None

    month = _climate_month(climate, constraints.start_date)
    picked_meals = [
        hit.row for hit in hits if hit.kind == "restaurant" and isinstance(hit.row, Restaurant)
    ]
    meals = meals_for_places(open_places, picked_meals, restaurants, price_band="budget")
    rebuilt = sequence_itinerary(
        open_places,
        meals,
        constraints,
        stay=stay,
        holidays=holidays,
        climate=month,
        stations=stations,
        edges=edges,
        fares=fares,
        place_pool=open_places,
    )
    rebuilt, swapped = _fit_stay(
        rebuilt,
        constraints,
        hotels,
        places,
        restaurant_by_id,
        bands,
        fares,
        buffer_pct,
        holidays,
        graph,
    )
    if swapped and rebuilt.stay is not None:
        notes.append(f"Replaced {stay.name} with {rebuilt.stay.name} so the stay costs less.")
    kept = _activity_ids(rebuilt)
    dropped = [place.name for place in open_places if place.id not in kept]
    if dropped:
        names = _unique(dropped)
        if len(names) == 1:
            joined = names[0]
        elif len(names) == 2:
            joined = f"{names[0]} and {names[1]}"
        else:
            joined = ", ".join(names[:-1]) + f", and {names[-1]}"
        notes.append(
            f"Moved aside {joined}, where the date, crowds, or neighborhood "
            "made the stop impractical."
        )
    notes.append(
        "Grouped the remaining stops by neighborhood and added meals where the day had none."
    )
    report = rebuilt.budget
    assert report is not None
    review = _review(constraints, rebuilt, report, places, restaurant_by_id, holidays)
    return rebuilt, notes, review


def _open_places(hits: list[_Hit]) -> list[Place]:
    chosen: list[Place] = []
    seen: set[str] = set()
    for hit in hits:
        if hit.kind != "place" or not isinstance(hit.row, Place):
            continue
        if hit.row.operational_status != "open" or hit.row.id in seen:
            continue
        seen.add(hit.row.id)
        chosen.append(hit.row)
    return chosen


def _fit_stay(
    itinerary: Itinerary,
    constraints: Constraints,
    hotels: list[Hotel],
    places: dict[str, Place],
    restaurants: dict[str, Restaurant],
    bands: list[PriceBand],
    fares: list[Fare],
    buffer_pct: float,
    holidays: list[Holiday],
    graph: TransitGraph,
) -> tuple[Itinerary, bool]:
    priced = _price(
        itinerary,
        constraints,
        places,
        restaurants,
        hotels,
        bands,
        fares,
        buffer_pct,
        holidays,
        graph,
    )
    itinerary.budget = priced
    if constraints.budget_aed is None or priced.within_budget or itinerary.stay is None:
        return itinerary, False
    cheap = _cheapest(hotels, constraints.model_copy(update={"hotel_tier": "budget"}), None)
    if cheap.id == itinerary.stay.id:
        return itinerary, False
    previous = itinerary.stay.id
    nxt = cheap.stay_option(season_for(constraints.start_date))
    if midpoint(nxt.nightly_min_aed, nxt.nightly_max_aed) >= midpoint(
        itinerary.stay.nightly_min_aed,
        itinerary.stay.nightly_max_aed,
    ):
        return itinerary, False
    for day in itinerary.days:
        for slot in day.slots:
            if slot.place_id == previous:
                slot.place_id = nxt.id
    itinerary.stay = nxt
    itinerary.budget = _price(
        itinerary,
        constraints,
        places,
        restaurants,
        hotels,
        bands,
        fares,
        buffer_pct,
        holidays,
        graph,
    )
    return itinerary, True


def _activity_ids(itinerary: Itinerary) -> set[str]:
    return {
        slot.place_id
        for day in itinerary.days
        for slot in day.slots
        if slot.kind == "activity" and slot.place_id
    }


def _climate_month(climate: list[ClimateMonth], start: date | None) -> ClimateMonth | None:
    if start is None:
        return None
    return next((row for row in climate if row.month == start.month), None)


def _unknown_findings(unknown: list[str]) -> list[AuditFinding]:
    return [
        AuditFinding(
            code="not_in_catalog",
            severity="blocker",
            title=_TITLES["not_in_catalog"],
            detail=f"“{name}” is not in our Dubai list, so we cannot price it or route to it.",
        )
        for name in unknown
    ]


def _from_review(report: ReviewReport | None, names: dict[str, str]) -> list[AuditFinding]:
    if report is None:
        return []
    findings: list[AuditFinding] = []
    for row in report.violations:
        detail = row.detail
        for place_id, name in names.items():
            detail = detail.replace(place_id, name)
        findings.append(
            AuditFinding(
                code=row.rule,
                severity=row.severity,
                title=_TITLES.get(row.rule, "A planning check failed"),
                detail=detail,
            )
        )
    return findings


def _recognized(hit: _Hit) -> RecognizedStop:
    status = hit.row.operational_status if isinstance(hit.row, Place) else "open"
    return RecognizedStop(
        name=hit.name,
        kind=hit.kind,
        area=hit.row.area,
        day=hit.day,
        status=status,
    )


def _assumptions(constraints: Constraints, stay: StayOption, unknown: list[str]) -> list[str]:
    notes = [
        "Places are matched by name to our Dubai list. This is not a booking or a ticket hold.",
        "Prices are estimated unless a line is marked verified. Flights are not included.",
        f"The stay used for the first cost check is {stay.name}.",
    ]
    if constraints.budget_aed is not None:
        amount = f"{constraints.budget_aed:g}"
        notes.append(
            f"The budget was read as AED {amount} for the whole group, including the hotel."
        )
    else:
        notes.append("No budget figure was found, so the cost is shown without a pass or fail.")
    if constraints.start_date is not None:
        notes.append(
            f"Dates start on {constraints.start_date.isoformat()} for {constraints.days} days."
        )
    else:
        notes.append("No start date was found, so holiday rules were not applied.")
    if constraints.avoid_crowds:
        notes.append("The plan asks to avoid crowds, so busy holiday stops count as a problem.")
    if unknown:
        notes.append("Unmatched names are listed on their own and left out of the rebuilt plan.")
    return notes


def _labels(
    places: list[Place],
    restaurants: list[Restaurant],
    hotels: list[Hotel],
) -> dict[str, dict[str, object]]:
    labels: dict[str, dict[str, object]] = {}
    for place in places:
        labels[place.id] = {
            "name": place.name,
            "area": place.area,
            "lat": place.lat,
            "lng": place.lng,
            "kind": "place",
            "category": place.category,
            "operational_status": place.operational_status,
        }
    for restaurant in restaurants:
        labels[restaurant.id] = {
            "name": restaurant.name,
            "area": restaurant.area,
            "lat": restaurant.lat,
            "lng": restaurant.lng,
            "kind": "restaurant",
            "category": restaurant.price_band,
            "operational_status": "open",
        }
    for hotel in hotels:
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


def _story(
    findings: list[AuditFinding],
    unknown: list[str],
    original_passed: bool,
    repaired_passed: bool,
    has_repair: bool,
) -> tuple[Verdict, str, str]:
    blockers = sum(1 for row in findings if row.severity == "blocker")
    if original_passed and not unknown:
        return (
            "clear",
            "This plan holds up",
            "The named places are on our Dubai list, the schedule passes the practical checks, "
            "and the estimated cost fits the budget we could read.",
        )
    if has_repair and repaired_passed:
        return (
            "repaired",
            "This plan had problems. Here is a version that passes.",
            "We checked the names, the hours, the travel, the holidays, and the cost. "
            f"The pasted version has {blockers} blocking issue{'s' if blockers != 1 else ''}. "
            "The rebuilt days keep only places we can stand behind.",
        )
    extra = " The rebuilt plan is below, with anything we still cannot clear."
    if not has_repair:
        extra = " There was not an open place left to rebuild a day around."
    return (
        "still_blocked",
        "A chatbot would sound sure. These checks are not.",
        "We matched the names to our Dubai list, then priced and scheduled only the real stops. "
        f"{blockers} blocking issue{'s' if blockers != 1 else ''} remain in the pasted plan."
        + extra,
    )
