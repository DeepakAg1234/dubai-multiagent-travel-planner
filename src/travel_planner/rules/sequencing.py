"""Cluster places by area, order them, and stamp time windows."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, time, timedelta

from travel_planner.data.areas import AREA_NEIGHBOUR, neighbour_area
from travel_planner.models import (
    ClimateMonth,
    Constraints,
    DayPlan,
    Fare,
    Holiday,
    Itinerary,
    Leg,
    Place,
    Restaurant,
    Slot,
    StayOption,
    TransitEdge,
    TransitStation,
)
from travel_planner.rules.fares import TransitGraph, route_leg
from travel_planner.rules.geo import distance_km
from travel_planner.rules.holidays import (
    apply_day_notes,
    effects_on,
    places_for_day,
    restaurants_for_day,
)
from travel_planner.rules.hours import add_minutes, minutes_between, overlaps, window_on

DAY_START = time(9, 0)
DAY_END = time(21, 30)
LUNCH_START = time(12, 30)
LUNCH_MINUTES = 60
DINNER_START = time(19, 0)
DINNER_MINUTES = 75
HEAT_START = time(12, 0)
HEAT_END = time(16, 0)
HEAT_C = 35.0
DEFAULT_VISIT = 60
CHECKIN = time(15, 0)
CHECKOUT = time(11, 0)
TRANSFER_PAD = 5
THIN_AREAS = frozenset(AREA_NEIGHBOUR)


def cluster_area(area: str) -> str:
    return neighbour_area(area)


def group_by_day(
    places: list[Place],
    days: int,
    *,
    pool: list[Place] | None = None,
) -> list[list[Place]]:
    """One cluster per planning-area neighbour. Thin areas share a Metro neighbour."""

    buckets: dict[str, list[Place]] = {}
    for place in places:
        if place.operational_status in {"closed", "reopening"}:
            continue
        buckets.setdefault(cluster_area(place.area), []).append(place)
    clusters = [
        buckets[key] for key in sorted(buckets, key=lambda name: (-len(buckets[name]), name))
    ]
    if not clusters and pool:
        extra = [row for row in pool if row.operational_status == "open"][: max(1, days)]
        if extra:
            clusters = [extra[:]]
    while len(clusters) < days:
        donor_index = (
            max(range(len(clusters)), key=lambda i: len(clusters[i])) if clusters else None
        )
        if donor_index is None or len(clusters[donor_index]) <= 1:
            borrowed = _borrow(clusters, pool, days - len(clusters))
            if borrowed:
                clusters.extend(borrowed)
                continue
            break
        donor = clusters[donor_index]
        if len(donor) < 2:
            break
        clusters.append([donor.pop()])
    while len(clusters) > days:
        last = clusters.pop()
        clusters[-1].extend(last)
    while len(clusters) < days:
        clusters.append([])
    return clusters[:days]


def _borrow(
    clusters: list[list[Place]],
    pool: list[Place] | None,
    needed: int,
) -> list[list[Place]]:
    if not pool or needed <= 0:
        return []
    used = {place.id for group in clusters for place in group}
    extras = [row for row in pool if row.id not in used and row.operational_status == "open"]
    out: list[list[Place]] = []
    for place in extras[:needed]:
        out.append([place])
    return out


def nearest_neighbour(
    places: list[Place],
    tie_rank: dict[str, int] | None = None,
) -> list[Place]:
    if len(places) <= 2:
        return list(places)
    remaining = places[1:]
    order = [places[0]]
    while remaining:
        current = order[-1]

        def key(row: Place, origin: Place = current) -> tuple[float, int]:
            rank = 0 if tie_rank is None else tie_rank.get(row.id, 10_000)
            return (distance_km(origin, row), rank)

        nxt = min(remaining, key=key)
        remaining.remove(nxt)
        order.append(nxt)
    return order


def two_opt(order: list[Place]) -> list[Place]:
    if len(order) < 4:
        return order
    best = list(order)

    def length(rows: list[Place]) -> float:
        return sum(distance_km(rows[i], rows[i + 1]) for i in range(len(rows) - 1))

    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for k in range(i + 2, len(best)):
                candidate = best[: i + 1] + list(reversed(best[i + 1 : k + 1])) + best[k + 1 :]
                if length(candidate) + 1e-9 < length(best):
                    best = candidate
                    improved = True
    return best


def order_places(
    places: list[Place],
    tie_rank: dict[str, int] | None = None,
) -> list[Place]:
    if not places:
        return []

    def rank(row: Place) -> tuple[float, float, int]:
        preference = tie_rank.get(row.id, 0) if tie_rank else 0
        return (row.lng, row.lat, preference)

    seed = min(places, key=rank)
    rest = [row for row in places if row.id != seed.id]
    return two_opt(nearest_neighbour([seed, *rest], tie_rank))


def _climate_high(month: ClimateMonth | None, start: date | None) -> float | None:
    if month is not None:
        return month.avg_high_c
    _ = start
    return None


def sequence_itinerary(
    places: list[Place],
    restaurants: list[Restaurant],
    constraints: Constraints,
    *,
    stay: StayOption | None = None,
    holidays: list[Holiday] | None = None,
    climate: ClimateMonth | None = None,
    stations: list[TransitStation] | None = None,
    edges: list[TransitEdge] | None = None,
    fares: list[Fare] | None = None,
    place_pool: list[Place] | None = None,
    tie_rank: dict[str, int] | None = None,
    resolve_leg: Callable[[Place, Place, time], Leg] | None = None,
) -> Itinerary:
    holidays = holidays or []
    fares = fares or []
    graph = TransitGraph(stations or [], edges or []) if stations and edges else None
    start = constraints.start_date
    heat = _climate_high(climate, start)
    hot = heat is not None and heat >= HEAT_C

    clusters = group_by_day(places, constraints.days, pool=place_pool)
    day_plans: list[DayPlan] = []
    for index, cluster in enumerate(clusters, start=1):
        day = start + timedelta(days=index - 1) if start else date(2026, 11, 18)
        effects = effects_on(holidays, day) if start else None
        allowed = places_for_day(cluster, effects, avoid_crowds=constraints.avoid_crowds)
        if not allowed:
            anchor = cluster_area(cluster[0].area) if cluster else "Downtown"
            pool_rows = [row for row in (place_pool or []) if cluster_area(row.area) == anchor]
            borrowed = places_for_day(pool_rows, effects, avoid_crowds=constraints.avoid_crowds)
            used = {place.id for place in cluster}
            allowed = [row for row in borrowed if row.id not in used][:2]
        meal_area = (
            cluster_area(allowed[0].area)
            if allowed
            else cluster_area(cluster[0].area)
            if cluster
            else "Downtown"
        )
        meals = restaurants_for_day(
            [row for row in restaurants if cluster_area(row.area) == meal_area],
            effects,
        )
        ordered = order_places(allowed, tie_rank)
        slots, legs = _schedule_day(
            index,
            ordered,
            meals,
            day,
            hot=hot,
            drop_lunch=bool(effects and effects.drop_lunch),
            stay=stay,
            last_day=index == constraints.days,
            graph=graph,
            fares=fares,
            resolve_leg=resolve_leg,
        )
        theme_area = (
            cluster_area(ordered[0].area)
            if ordered
            else (cluster_area(cluster[0].area) if cluster else "Dubai")
        )
        thin = any(place.area in THIN_AREAS for place in ordered)
        theme = (
            theme_area
            if not thin
            else (
                f"{theme_area} (with "
                f"{', '.join(sorted({p.area for p in ordered if p.area in THIN_AREAS}))})"
            )
        )
        day_plans.append(DayPlan(day=index, theme=theme, slots=slots, legs=legs))

    if start is not None:
        day_plans = apply_day_notes(day_plans, holidays, start)
    return Itinerary(days=day_plans, stay=stay)


def _schedule_day(
    day_number: int,
    places: list[Place],
    restaurants: list[Restaurant],
    day: date,
    *,
    hot: bool,
    drop_lunch: bool,
    stay: StayOption | None,
    last_day: bool,
    graph: TransitGraph | None,
    fares: list[Fare],
    resolve_leg: Callable[[Place, Place, time], Leg] | None = None,
) -> tuple[list[Slot], list[Leg]]:
    slots: list[Slot] = []
    legs: list[Leg] = []
    cursor = DAY_START
    previous: Place | None = None
    lunch_done = drop_lunch
    dinner_done = False

    if day_number > 1 and stay is not None and last_day:
        slots.append(
            Slot(start=CHECKOUT, end=add_minutes(CHECKOUT, 20), place_id=stay.id, kind="checkout")
        )
        if cursor < add_minutes(CHECKOUT, 20):
            cursor = add_minutes(CHECKOUT, 20)

    lunch_place = _pick_meal(restaurants, "lunch")
    dinner_place = _pick_meal(restaurants, "dinner", excluding=lunch_place)

    for place in places:
        if not lunch_done and lunch_place is not None and cursor >= time(11, 45):
            cursor, previous = _append_stop(
                slots,
                legs,
                cursor,
                previous,
                lunch_place,
                kind="meal",
                minutes=LUNCH_MINUTES,
                notes="lunch",
                day=day,
                graph=graph,
                fares=fares,
                resolve_leg=resolve_leg,
                indoor=True,
            )
            lunch_done = True

        visit = place.typical_visit_minutes or DEFAULT_VISIT
        would_hit_heat = overlaps(cursor, add_minutes(cursor, visit), HEAT_START, HEAT_END)
        if hot and place.indoor is False and would_hit_heat:
            rest_end = HEAT_END
            rest_start = cursor if cursor >= HEAT_START else HEAT_START
            if rest_start < rest_end:
                slots.append(
                    Slot(
                        start=rest_start,
                        end=rest_end,
                        place_id=stay.id if stay else None,
                        kind="rest",
                        notes="Midday heat rest; outdoor activities resume after 16:00",
                    )
                )
            cursor = rest_end

        if place.timed_entry:
            notes = "Timed entry; no ticket hold."
        else:
            notes = None
        cursor, previous = _append_stop(
            slots,
            legs,
            cursor,
            previous,
            place,
            kind="activity",
            minutes=visit,
            notes=notes,
            day=day,
            graph=graph,
            fares=fares,
            resolve_leg=resolve_leg,
            indoor=bool(place.indoor),
        )

    if not lunch_done and lunch_place is not None and cursor < time(15, 0):
        cursor, previous = _append_stop(
            slots,
            legs,
            cursor,
            previous,
            lunch_place,
            kind="meal",
            minutes=LUNCH_MINUTES,
            notes="lunch",
            day=day,
            graph=graph,
            fares=fares,
            resolve_leg=resolve_leg,
            indoor=True,
        )
        lunch_done = True

    if day_number == 1 and stay is not None and cursor <= CHECKIN:
        slots.append(
            Slot(start=CHECKIN, end=add_minutes(CHECKIN, 20), place_id=stay.id, kind="checkin")
        )
        if cursor < add_minutes(CHECKIN, 20):
            cursor = add_minutes(CHECKIN, 20)

    if dinner_place is not None and not dinner_done:
        if cursor < DINNER_START:
            cursor = DINNER_START
        _append_stop(
            slots,
            legs,
            cursor,
            previous,
            dinner_place,
            kind="meal",
            minutes=DINNER_MINUTES,
            notes="dinner",
            day=day,
            graph=graph,
            fares=fares,
            resolve_leg=resolve_leg,
            indoor=True,
        )

    return slots, legs


def _pick_meal(
    restaurants: list[Restaurant],
    meal: str,
    excluding: Restaurant | None = None,
) -> Restaurant | None:
    for row in restaurants:
        if excluding is not None and row.id == excluding.id:
            continue
        if meal in row.meal_types:
            return row
    for row in restaurants:
        if meal in row.meal_types:
            return row
    return None


def _append_stop(
    slots: list[Slot],
    legs: list[Leg],
    cursor: time,
    previous: Place | None,
    stop: Place | Restaurant,
    *,
    kind: str,
    minutes: int,
    notes: str | None,
    day: date,
    graph: TransitGraph | None,
    fares: list[Fare],
    indoor: bool,
    resolve_leg: Callable[[Place, Place, time], Leg] | None = None,
) -> tuple[time, Place]:
    as_place = _as_place(stop)
    if previous is not None:
        if resolve_leg is not None:
            leg = resolve_leg(previous, as_place, cursor)
        else:
            leg = route_leg(previous, as_place, graph, fares, when=cursor)
        transfer_end = add_minutes(cursor, leg.minutes + TRANSFER_PAD)
        slots.append(
            Slot(
                start=cursor,
                end=transfer_end,
                place_id=None,
                kind="transfer",
                notes=f"{leg.mode}, {leg.minutes} min",
            )
        )
        legs.append(leg)
        cursor = transfer_end

    window = window_on(stop.opening_hours, day)
    if window is not None and cursor < window[0]:
        cursor = window[0]
    end = add_minutes(cursor, minutes)
    if window is not None and end > window[1] and window[1] > cursor:
        end = window[1]
    slots.append(
        Slot(
            start=cursor,
            end=end,
            place_id=stop.id,
            kind=kind,  # type: ignore[arg-type]
            notes=notes,
        )
    )
    _ = indoor
    return end, as_place


def _as_place(row: Place | Restaurant) -> Place:
    if isinstance(row, Place):
        return row
    return Place(
        id=row.id,
        name=row.name,
        category="restaurant",
        area=row.area,
        lat=row.lat,
        lng=row.lng,
        provenance=row.provenance,
        source=row.source,
        as_of=row.as_of,
        opening_hours=row.opening_hours,
        indoor=True,
        operational_status="open",
    )


def active_minutes(day: DayPlan) -> int:
    return sum(
        minutes_between(slot.start, slot.end)
        for slot in day.slots
        if slot.kind in {"activity", "meal", "transfer"}
    )
