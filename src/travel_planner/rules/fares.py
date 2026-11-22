"""Silver Nol fares, taxi, Abra, and the offline Metro/tram graph.

Stations in the seed have no RTA zone. Zone span comes from this planner-side
map (estimated) unless a later seed fill lands.
"""

from __future__ import annotations

import heapq
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, time
from typing import Literal

from travel_planner.models import Fare, Leg, Place, TransitEdge, TransitStation
from travel_planner.models.catalog import TransportMode
from travel_planner.rules.geo import distance_km, taxi_minutes, walk_minutes

# Estimated Nol zones from planning area. Not read from TransitStation.zone.
AREA_NOL_ZONE: dict[str, int] = {
    "Old Dubai": 1,
    "Dubai Creek": 1,
    "Downtown": 2,
    "Business Bay": 2,
    "Jumeirah": 2,
    "Al Quoz": 2,
    "Marina / JBR": 3,
    "Palm": 3,
}

WATERFRONT_AREAS = frozenset({"Old Dubai", "Dubai Creek"})
NIGHT_START = time(22, 0)
NIGHT_END = time(6, 0)
WALK_TO_STATION_KM = 1.2
WALK_DIRECT_KM = 0.8
ABRA_MIN_KM = 0.25
ABRA_MAX_KM = 2.5
FARE_SOURCE = "planner:rules/fares.py area-to-zone map (estimated)"

PassChoice = Literal["pay_per_trip", "red_1day", "silver_7day"]


def nol_zone_for_area(area: str) -> int:
    if area in AREA_NOL_ZONE:
        return AREA_NOL_ZONE[area]
    return 2


def nol_zone_for_point(lat: float, lng: float) -> int:
    """Coarse east-west split matching Deira / Downtown / Marina."""

    if lng >= 55.31:
        return 1
    if lng >= 55.25:
        return 2
    return 3


def nol_zone_for_station(station: TransitStation) -> int:
    return nol_zone_for_point(station.lat, station.lng)


def zone_span(zone_a: int, zone_b: int) -> int:
    return abs(zone_a - zone_b) + 1


def span_rule(span: int) -> str:
    if span <= 1:
        return "1"
    if span == 2:
        return "2"
    return "3+"


def _fare_lookup(fares: Iterable[Fare], *, mode: str, card: str, zone_rule: str) -> Fare | None:
    for row in fares:
        if row.mode == mode and row.card_type == card and row.zone_rule == zone_rule:
            return row
    return None


def silver_metro_fare(fares: Iterable[Fare], span: int) -> Fare:
    rule = span_rule(span)
    found = _fare_lookup(fares, mode="metro", card="silver", zone_rule=rule)
    if found is None:
        price = {1: 3.0, 2: 5.0}.get(span, 7.5)
        return Fare(
            id=f"fallback-silver-{rule}",
            mode="metro",
            zone_rule=rule,
            price_aed=price,
            card_type="silver",
            provenance="estimated",
            source=FARE_SOURCE,
            as_of=date(2026, 11, 16),
        )
    return found


def pass_1day(fares: Iterable[Fare]) -> Fare:
    found = _fare_lookup(fares, mode="metro", card="red_1day", zone_rule="all")
    if found is not None:
        return found
    return Fare(
        id="fallback-1day",
        mode="metro",
        zone_rule="all",
        price_aed=20.0,
        card_type="red_1day",
        provenance="estimated",
        source=FARE_SOURCE,
        as_of=date(2026, 11, 16),
    )


def pass_7day(fares: Iterable[Fare], span: int) -> Fare:
    rule = "1" if span <= 1 else "2" if span == 2 else "all"
    found = _fare_lookup(fares, mode="metro", card="silver_7day", zone_rule=rule)
    if found is not None:
        return found
    price = 50.0 if span <= 1 else 80.0 if span == 2 else 110.0
    return Fare(
        id=f"fallback-7day-{rule}",
        mode="metro",
        zone_rule=rule,
        price_aed=price,
        card_type="silver_7day",
        provenance="verified",
        source=FARE_SOURCE,
        as_of=date(2026, 11, 16),
    )


def taxi_flag(fares: Iterable[Fare], when: time | None) -> Fare:
    night = when is not None and (when >= NIGHT_START or when < NIGHT_END)
    rule = "flag_22_06" if night else "flag_06_22"
    found = _fare_lookup(fares, mode="taxi", card="street_hail", zone_rule=rule)
    if found is not None:
        return found
    return Fare(
        id="fallback-taxi-flag",
        mode="taxi",
        zone_rule=rule,
        price_aed=5.5 if night else 5.0,
        card_type="street_hail",
        provenance="estimated",
        source=FARE_SOURCE,
        as_of=date(2026, 11, 16),
    )


def _taxi_component(fares: Iterable[Fare], zone_rule: str, default: float) -> Fare:
    found = _fare_lookup(fares, mode="taxi", card="street_hail", zone_rule=zone_rule)
    if found is not None:
        return found
    return Fare(
        id=f"fallback-taxi-{zone_rule}",
        mode="taxi",
        zone_rule=zone_rule,
        price_aed=default,
        card_type="street_hail",
        provenance="estimated",
        source=FARE_SOURCE,
        as_of=date(2026, 11, 16),
    )


def taxi_fare_aed(fares: Iterable[Fare], km: float, when: time | None = None) -> tuple[float, Fare]:
    flag = taxi_flag(fares, when)
    per_km = _taxi_component(fares, "per_km", 2.45)
    minimum = _taxi_component(fares, "minimum", 12.0)
    raw = flag.price_aed + per_km.price_aed * max(0.0, km)
    total = max(raw, minimum.price_aed)
    return round(total, 2), flag


def abra_fare(fares: Iterable[Fare]) -> Fare:
    found = _fare_lookup(fares, mode="ferry", card="cash", zone_rule="fixed")
    if found is not None:
        return found
    return Fare(
        id="fallback-abra",
        mode="ferry",
        zone_rule="fixed",
        price_aed=1.0,
        card_type="cash",
        provenance="estimated",
        source=FARE_SOURCE,
        as_of=date(2026, 11, 16),
    )


def is_night(when: time | None) -> bool:
    if when is None:
        return False
    return when >= NIGHT_START or when < NIGHT_END


def is_abra_crossing(from_area: str, to_area: str, km: float) -> bool:
    return (
        from_area in WATERFRONT_AREAS
        and to_area in WATERFRONT_AREAS
        and ABRA_MIN_KM <= km <= ABRA_MAX_KM
    )


@dataclass(frozen=True)
class GraphHop:
    to_id: str
    minutes: int
    line: str


class TransitGraph:
    """Dijkstra over curated edges. Missing reverses are added so lines are rideable both ways."""

    def __init__(self, stations: list[TransitStation], edges: list[TransitEdge]) -> None:
        self.stations = {row.id: row for row in stations}
        self._adj: dict[str, list[GraphHop]] = defaultdict(list)
        seen: set[tuple[str, str]] = set()
        for edge in edges:
            self._add(edge.from_id, edge.to_id, edge.minutes, edge.line, seen)
            self._add(edge.to_id, edge.from_id, edge.minutes, edge.line, seen)

    def _add(
        self, start: str, end: str, minutes: int, line: str, seen: set[tuple[str, str]]
    ) -> None:
        key = (start, end)
        if key in seen:
            return
        seen.add(key)
        self._adj[start].append(GraphHop(end, minutes, line))

    def minutes(self, from_id: str, to_id: str) -> tuple[int, list[str]] | None:
        if from_id not in self.stations or to_id not in self.stations:
            return None
        if from_id == to_id:
            return 0, []
        dist: dict[str, int] = {from_id: 0}
        prev: dict[str, tuple[str, str]] = {}
        heap: list[tuple[int, str]] = [(0, from_id)]
        while heap:
            cost, node = heapq.heappop(heap)
            if node == to_id:
                return cost, _lines(prev, from_id, to_id)
            if cost > dist.get(node, 10**9):
                continue
            for hop in self._adj.get(node, []):
                nxt = cost + hop.minutes
                if nxt < dist.get(hop.to_id, 10**9):
                    dist[hop.to_id] = nxt
                    prev[hop.to_id] = (node, hop.line)
                    heapq.heappush(heap, (nxt, hop.to_id))
        return None

    def nearest_station(self, place: Place) -> TransitStation | None:
        if not self.stations:
            return None
        return min(self.stations.values(), key=lambda row: distance_km(place, row))


def _lines(prev: dict[str, tuple[str, str]], start: str, end: str) -> list[str]:
    lines: list[str] = []
    node = end
    while node != start:
        parent, line = prev[node]
        lines.append(line)
        node = parent
    lines.reverse()
    return lines


def _mode_from_lines(lines: list[str]) -> TransportMode:
    if any(line.lower() == "tram" for line in lines) and not any(
        line.lower() in {"red", "green"} for line in lines
    ):
        return "tram"
    if any(line.lower() == "walk" for line in lines) and all(
        line.lower() == "walk" for line in lines
    ):
        return "walk"
    return "metro"


def route_leg(
    origin: Place,
    dest: Place,
    graph: TransitGraph | None,
    fares: Iterable[Fare],
    *,
    when: time | None = None,
    prefer: TransportMode | None = None,
) -> Leg:
    """Graph minutes when a path exists; otherwise straight-line walk or taxi."""

    km = distance_km(origin, dest)
    if prefer == "bus":
        prefer = None if graph and graph.nearest_station(origin) else "taxi"

    if prefer == "walk" or (prefer is None and km <= WALK_DIRECT_KM):
        return _leg(origin, dest, "walk", walk_minutes(km), km, 0.0, estimated=True)

    if prefer in {None, "ferry"} and is_abra_crossing(origin.area, dest.area, km):
        fare = abra_fare(fares)
        minutes = max(8, walk_minutes(km * 0.6))
        return _leg(
            origin,
            dest,
            "ferry",
            minutes,
            km,
            fare.price_aed,
            provenance=fare.provenance,
            source=fare.source,
            as_of=fare.as_of,
        )

    metro = (
        _metro_leg(origin, dest, graph, fares, km) if prefer in {None, "metro", "tram"} else None
    )
    if metro is not None and prefer in {"metro", "tram"}:
        return metro
    if metro is not None and prefer is None:
        taxi_cost, taxi_row = taxi_fare_aed(fares, km, when)
        taxi_time = taxi_minutes(km)
        if taxi_time + 8 < metro.minutes and km > 3:
            return _leg(
                origin,
                dest,
                "taxi",
                taxi_time,
                km,
                taxi_cost,
                provenance=taxi_row.provenance,
                source=taxi_row.source,
                as_of=taxi_row.as_of,
            )
        return metro

    taxi_cost, taxi_row = taxi_fare_aed(fares, km, when)
    return _leg(
        origin,
        dest,
        "taxi",
        taxi_minutes(km),
        km,
        taxi_cost,
        provenance=taxi_row.provenance,
        source=taxi_row.source,
        as_of=taxi_row.as_of,
    )


def _metro_leg(
    origin: Place,
    dest: Place,
    graph: TransitGraph | None,
    fares: Iterable[Fare],
    km: float,
) -> Leg | None:
    if graph is None:
        return None
    start = graph.nearest_station(origin)
    end = graph.nearest_station(dest)
    if start is None or end is None:
        return None
    if (
        distance_km(origin, start) > WALK_TO_STATION_KM
        or distance_km(dest, end) > WALK_TO_STATION_KM
    ):
        return None
    path = graph.minutes(start.id, end.id)
    if path is None:
        return None
    ride, lines = path
    access = walk_minutes(distance_km(origin, start)) + walk_minutes(distance_km(dest, end))
    span = zone_span(nol_zone_for_station(start), nol_zone_for_station(end))
    fare = silver_metro_fare(fares, span)
    mode = _mode_from_lines(lines) if start.id != end.id else "walk"
    cost = 0.0 if mode == "walk" else fare.price_aed
    return _leg(
        origin,
        dest,
        mode,
        ride + access,
        km,
        cost,
        provenance=fare.provenance if cost else "estimated",
        source=fare.source if cost else "curated:transit_edges.json",
        as_of=fare.as_of,
    )


def _leg(
    origin: Place,
    dest: Place,
    mode: TransportMode,
    minutes: int,
    km: float,
    cost: float,
    *,
    provenance: str = "estimated",
    source: str = FARE_SOURCE,
    as_of: date | None = date(2026, 11, 16),
    estimated: bool = False,
) -> Leg:
    _ = estimated
    return Leg(
        from_id=origin.id,
        to_id=dest.id,
        mode=mode,
        minutes=max(0, minutes),
        distance_km=round(km, 3),
        cost_aed=cost,
        provenance=provenance,  # type: ignore[arg-type]
        source=source,
        as_of=as_of,
    )


@dataclass(frozen=True)
class TransitPassPlan:
    choice: PassChoice
    unit_aed: float
    quantity: float
    total_aed: float
    pay_per_trip_aed: float
    provenance: str
    source: str
    as_of: date | None
    item: str
    trip_span: int


def trip_zone_span(areas: Iterable[str]) -> int:
    zones = [nol_zone_for_area(area) for area in areas]
    if not zones:
        return 1
    return max(zones) - min(zones) + 1


def choose_transit_pass(
    metro_trip_fares: list[float],
    *,
    days: int,
    span: int,
    fares: Iterable[Fare],
    travelers: int = 1,
) -> TransitPassPlan:
    """Compare Silver pay-per-trip, the estimated 1-day pass, and the Silver 7-day pass.

    There is no unpublished daily Silver cap.
    """

    pay = round(sum(metro_trip_fares) * travelers, 2)
    day_pass = pass_1day(fares)
    week = pass_7day(fares, span)
    day_total = round(day_pass.price_aed * max(1, days) * travelers, 2)
    week_total = round(week.price_aed * travelers, 2)

    options: list[tuple[float, PassChoice, Fare, float, str]] = [
        (
            pay,
            "pay_per_trip",
            silver_metro_fare(fares, span),
            float(len(metro_trip_fares) * travelers),
            "Silver pay-per-trip",
        ),
        (day_total, "red_1day", day_pass, float(max(1, days) * travelers), "Red Ticket 1-day pass"),
        (
            week_total,
            "silver_7day",
            week,
            float(travelers),
            f"Silver 7-day pass ({week.zone_rule} zones)",
        ),
    ]
    total, choice, fare, qty, item = min(
        options, key=lambda row: (row[0], 0 if row[1] == "pay_per_trip" else 1)
    )
    return TransitPassPlan(
        choice=choice,
        unit_aed=fare.price_aed if choice != "pay_per_trip" else (pay / qty if qty else 0.0),
        quantity=qty,
        total_aed=total,
        pay_per_trip_aed=pay,
        provenance=fare.provenance if choice != "pay_per_trip" else "verified",
        source=fare.source,
        as_of=fare.as_of,
        item=item,
        trip_span=span,
    )


def price_existing_leg(leg: Leg, fares: Iterable[Fare], *, when: time | None = None) -> Leg:
    """Fill cost on a draft leg. Bus becomes Metro when possible, otherwise taxi."""

    if leg.mode in {"walk", "drive"}:
        return leg.model_copy(update={"cost_aed": 0.0})
    if leg.cost_aed is not None and leg.mode != "bus":
        return leg
    if leg.mode == "ferry":
        fare = abra_fare(fares)
        return leg.model_copy(
            update={
                "cost_aed": fare.price_aed,
                "provenance": fare.provenance,
                "source": fare.source,
            }
        )
    if leg.mode in {"metro", "tram", "bus"}:
        span = 2
        fare = silver_metro_fare(fares, span)
        mode: TransportMode = "metro" if leg.mode == "bus" else leg.mode
        return leg.model_copy(
            update={
                "mode": mode,
                "cost_aed": fare.price_aed,
                "provenance": fare.provenance,
                "source": fare.source,
            }
        )
    cost, fare = taxi_fare_aed(fares, leg.distance_km, when)
    return leg.model_copy(
        update={
            "cost_aed": cost,
            "provenance": fare.provenance,
            "source": fare.source,
            "mode": "taxi",
        }
    )
