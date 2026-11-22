"""Deterministic budget lines. LLMs do not invent prices."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from travel_planner.data.areas import neighbour_area
from travel_planner.models import (
    Alternative,
    BudgetLine,
    BudgetReport,
    Constraints,
    Fare,
    Hotel,
    Itinerary,
    Place,
    PriceBand,
    Restaurant,
    StayOption,
)
from travel_planner.models.catalog import HotelTier, Season
from travel_planner.rules.fares import (
    TransitGraph,
    choose_transit_pass,
    price_existing_leg,
    route_leg,
    trip_zone_span,
)

SUMMER_MONTHS = frozenset({5, 6, 7, 8, 9})
CHEAP_PLACE_AED = 20.0
TIER_BELOW: dict[HotelTier, HotelTier | None] = {
    "luxury": "mid",
    "mid": "budget",
    "budget": None,
}
FOOD_TIER_BELOW = {"upscale": "mid", "mid": "budget"}
BUFFER_SOURCE = "config:BUFFER_PCT"


def season_for(day: date | None) -> Season:
    if day is None:
        return "peak"
    return "summer" if day.month in SUMMER_MONTHS else "peak"


def midpoint(low: float, high: float) -> float:
    return round((low + high) / 2, 2)


def stay_nightly_mid(stay: StayOption) -> float:
    return midpoint(stay.nightly_min_aed, stay.nightly_max_aed)


def nights_for(constraints: Constraints) -> int:
    return max(1, constraints.days)


def food_band(bands: Sequence[PriceBand], tier: str) -> PriceBand | None:
    for row in bands:
        if row.category == "food" and row.tier == tier:
            return row
    return None


def accommodation_line(stay: StayOption, nights: int, travelers: int = 1) -> BudgetLine:
    _ = travelers
    unit = stay_nightly_mid(stay)
    return BudgetLine(
        category="accommodation",
        item=f"{stay.name} ({stay.season}, {nights} night{'s' if nights != 1 else ''})",
        unit_aed=unit,
        quantity=float(nights),
        total_aed=round(unit * nights, 2),
        provenance=stay.provenance,
        source=stay.source,
        as_of=stay.as_of,
    )


def food_lines(
    restaurants: Sequence[Restaurant],
    bands: Sequence[PriceBand],
    travelers: int,
) -> list[BudgetLine]:
    lines: list[BudgetLine] = []
    for restaurant in restaurants:
        band = food_band(bands, restaurant.price_band)
        meals = [meal for meal in restaurant.meal_types if meal in {"lunch", "dinner"}]
        if not meals:
            continue
        if band is None:
            unit = 70.0
            provenance, source, as_of = "estimated", "curated:price_bands.json", restaurant.as_of
        else:
            unit = midpoint(band.min_aed, band.max_aed)
            provenance, source, as_of = band.provenance, band.source, band.as_of
        qty = float(len(meals) * travelers)
        lines.append(
            BudgetLine(
                category="food",
                item=f"{restaurant.name} ({', '.join(meals)})",
                unit_aed=unit,
                quantity=qty,
                total_aed=round(unit * qty, 2),
                provenance=provenance,  # type: ignore[arg-type]
                source=source,
                as_of=as_of,
            )
        )
    return lines


def food_lines_from_slots(
    days: Sequence,
    restaurants: dict[str, Restaurant],
    bands: Sequence[PriceBand],
    travelers: int,
) -> list[BudgetLine]:
    """One line per meal slot. Ramadan drafts simply have no lunch slots."""

    lines: list[BudgetLine] = []
    for day in days:
        for slot in day.slots:
            if slot.kind != "meal" or not slot.place_id:
                continue
            restaurant = restaurants.get(slot.place_id)
            if restaurant is None:
                continue
            band = food_band(bands, restaurant.price_band)
            if band is None:
                unit = 70.0
                provenance, source, as_of = (
                    "estimated",
                    "curated:price_bands.json",
                    restaurant.as_of,
                )
            else:
                unit = midpoint(band.min_aed, band.max_aed)
                provenance, source, as_of = band.provenance, band.source, band.as_of
            meal = (slot.notes or "meal").split(";")[0].strip() or "meal"
            qty = float(travelers)
            lines.append(
                BudgetLine(
                    category="food",
                    item=f"{restaurant.name} ({meal})",
                    unit_aed=unit,
                    quantity=qty,
                    total_aed=round(unit * qty, 2),
                    provenance=provenance,  # type: ignore[arg-type]
                    source=source,
                    as_of=as_of,
                )
            )
    return lines


def activity_lines(places: Sequence[Place], travelers: int) -> list[BudgetLine]:
    lines: list[BudgetLine] = []
    for place in places:
        if place.operational_status in {"closed", "reopening"}:
            continue
        max_aed = 0.0 if place.price_aed is None else place.price_aed.max_aed
        unit = max_aed
        qty = float(travelers)
        lines.append(
            BudgetLine(
                category="activities",
                item=place.name,
                unit_aed=unit,
                quantity=qty,
                total_aed=round(unit * qty, 2),
                provenance=place.provenance,
                source=place.source,
                as_of=place.as_of,
            )
        )
    return lines


def cheapest_budget_night(hotels: Sequence[Hotel], season: Season) -> float:
    budget = [row for row in hotels if row.tier == "budget"]
    if not budget:
        return 170.0 if season == "peak" else 120.0
    if season == "peak":
        return min(row.peak_nightly_min for row in budget)
    return min(row.summer_nightly_min for row in budget)


def minimum_trip_floor(
    *,
    nights: int,
    days: int,
    travelers: int,
    season: Season,
    hotels: Sequence[Hotel],
    bands: Sequence[PriceBand],
    buffer_pct: float,
    drop_lunch_days: int = 0,
) -> float:
    night = cheapest_budget_night(hotels, season)
    food = food_band(bands, "budget")
    meal_unit = food.min_aed if food else 25.0
    meals = max(0, days * 2 - drop_lunch_days)
    subtotal = night * nights + meal_unit * meals * travelers
    return round(subtotal * (1 + buffer_pct / 100), 2)


def _sum_category(lines: Sequence[BudgetLine]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for line in lines:
        totals[line.category] = round(totals.get(line.category, 0.0) + line.total_aed, 2)
    return totals


def _buffer_line(subtotal: float, buffer_pct: float) -> BudgetLine:
    total = round(subtotal * buffer_pct / 100, 2)
    return BudgetLine(
        category="buffer",
        item=f"{buffer_pct:g}% contingency",
        unit_aed=total,
        quantity=1,
        total_aed=total,
        provenance="estimated",
        source=BUFFER_SOURCE,
        as_of=None,
    )


def _places_from_itinerary(itinerary: Itinerary, places: dict[str, Place]) -> list[Place]:
    seen: list[Place] = []
    ids: set[str] = set()
    for day in itinerary.days:
        for slot in day.slots:
            if slot.kind != "activity" or not slot.place_id:
                continue
            if slot.place_id in ids:
                continue
            place = places.get(slot.place_id)
            if place is None:
                continue
            ids.add(place.id)
            seen.append(place)
    return seen


def compute_budget(
    itinerary: Itinerary,
    constraints: Constraints,
    *,
    places: dict[str, Place],
    restaurants: dict[str, Restaurant],
    hotels: Sequence[Hotel],
    bands: Sequence[PriceBand],
    fares: Sequence[Fare],
    buffer_pct: float = 10.0,
    drop_lunch_days: int = 0,
    graph: TransitGraph | None = None,
) -> BudgetReport:
    nights = nights_for(constraints)
    season = season_for(constraints.start_date)
    lines: list[BudgetLine] = []

    if itinerary.stay is not None:
        lines.append(accommodation_line(itinerary.stay, nights, constraints.travelers))

    lines.extend(food_lines_from_slots(itinerary.days, restaurants, bands, constraints.travelers))
    lines.extend(activity_lines(_places_from_itinerary(itinerary, places), constraints.travelers))

    priced_legs = [price_existing_leg(leg, fares) for day in itinerary.days for leg in day.legs]
    metro_costs = [
        (leg.cost_aed or 0.0) * constraints.travelers
        for leg in priced_legs
        if leg.mode in {"metro", "tram"}
    ]
    areas = [places[leg.from_id].area for leg in priced_legs if leg.from_id in places]
    areas += [places[leg.to_id].area for leg in priced_legs if leg.to_id in places]
    if itinerary.stay is not None:
        areas.append(itinerary.stay.area)
    span = trip_zone_span(areas)
    transit = choose_transit_pass(
        [c / constraints.travelers for c in metro_costs],
        days=constraints.days,
        span=span,
        fares=fares,
        travelers=constraints.travelers,
    )
    if transit.choice == "pay_per_trip":
        for leg in priced_legs:
            if (leg.cost_aed or 0) <= 0 and leg.mode in {"walk"}:
                continue
            if leg.mode in {"metro", "tram"}:
                cost = (leg.cost_aed or 0) * constraints.travelers
                lines.append(
                    BudgetLine(
                        category="transport",
                        item=f"{leg.mode} {leg.from_id} → {leg.to_id}",
                        unit_aed=leg.cost_aed or 0,
                        quantity=float(constraints.travelers),
                        total_aed=round(cost, 2),
                        provenance=leg.provenance,
                        source=leg.source,
                        as_of=leg.as_of,
                    )
                )
            elif leg.mode in {"taxi", "ferry"}:
                cost = (leg.cost_aed or 0) * constraints.travelers
                lines.append(
                    BudgetLine(
                        category="transport",
                        item=f"{leg.mode} {leg.from_id} → {leg.to_id}",
                        unit_aed=leg.cost_aed or 0,
                        quantity=float(constraints.travelers),
                        total_aed=round(cost, 2),
                        provenance=leg.provenance,
                        source=leg.source,
                        as_of=leg.as_of,
                    )
                )
    else:
        lines.append(
            BudgetLine(
                category="transport",
                item=transit.item,
                unit_aed=transit.unit_aed,
                quantity=transit.quantity,
                total_aed=transit.total_aed,
                provenance=transit.provenance,  # type: ignore[arg-type]
                source=transit.source,
                as_of=transit.as_of,
            )
        )
        for leg in priced_legs:
            if leg.mode in {"taxi", "ferry"} and (leg.cost_aed or 0) > 0:
                cost = (leg.cost_aed or 0) * constraints.travelers
                lines.append(
                    BudgetLine(
                        category="transport",
                        item=f"{leg.mode} {leg.from_id} → {leg.to_id}",
                        unit_aed=leg.cost_aed or 0,
                        quantity=float(constraints.travelers),
                        total_aed=round(cost, 2),
                        provenance=leg.provenance,
                        source=leg.source,
                        as_of=leg.as_of,
                    )
                )

    subtotal = round(sum(line.total_aed for line in lines), 2)
    lines.append(_buffer_line(subtotal, buffer_pct))
    total = round(sum(line.total_aed for line in lines), 2)
    budget_aed = constraints.budget_aed
    floor = minimum_trip_floor(
        nights=nights,
        days=constraints.days,
        travelers=constraints.travelers,
        season=season,
        hotels=hotels,
        bands=bands,
        buffer_pct=buffer_pct,
        drop_lunch_days=drop_lunch_days,
    )
    if budget_aed is not None and budget_aed < floor:
        lines.append(
            BudgetLine(
                category="buffer",
                item=f"minimum viable trip floor (cheapest budget {season} stay)",
                unit_aed=floor,
                quantity=1,
                total_aed=0,
                provenance="estimated",
                source="rules/budget.py hotel floor",
                as_of=None,
            )
        )
        total = round(sum(line.total_aed for line in lines), 2)

    variance = None if budget_aed is None else round(budget_aed - total, 2)
    within = True if budget_aed is None else total <= budget_aed
    if budget_aed is not None and budget_aed < floor:
        within = False
        variance = round(budget_aed - floor, 2)

    report = BudgetReport(
        lines=lines,
        by_category=_sum_category(lines),
        total_aed=total,
        budget_aed=budget_aed,
        variance_aed=variance,
        within_budget=within,
        alternatives=[],
    )
    report.alternatives = build_alternatives(
        report,
        itinerary,
        constraints,
        places=places,
        restaurants=restaurants,
        hotels=hotels,
        bands=bands,
        fares=fares,
        graph=graph,
        floor_aed=floor,
    )
    return report


def build_alternatives(
    report: BudgetReport,
    itinerary: Itinerary,
    constraints: Constraints,
    *,
    places: dict[str, Place],
    restaurants: dict[str, Restaurant],
    hotels: Sequence[Hotel],
    bands: Sequence[PriceBand],
    fares: Sequence[Fare],
    graph: TransitGraph | None,
    floor_aed: float,
) -> list[Alternative]:
    alts: list[Alternative] = []
    total = report.total_aed
    stay = itinerary.stay
    season = season_for(constraints.start_date)

    if stay is not None:
        lower = TIER_BELOW.get(stay.tier)
        same_area = [row for row in hotels if row.area == stay.area]
        candidates = [
            row
            for row in same_area
            if (lower is not None and row.tier == lower)
            or (row.tier == stay.tier and row.id != stay.id)
        ]
        if candidates:
            current = stay_nightly_mid(stay) * nights_for(constraints)
            best = min(candidates, key=lambda row: stay_nightly_mid(row.stay_option(season)))
            new_stay = best.stay_option(season)
            new_acc = stay_nightly_mid(new_stay) * nights_for(constraints)
            savings = round(current - new_acc, 2)
            if savings > 0:
                alts.append(
                    Alternative(
                        kind="cheaper_hotel",
                        description=f"Switch stay to {best.name} ({best.tier}) in {best.area}",
                        savings_aed=savings,
                        new_total_aed=round(max(0.0, total - savings), 2),
                        replaces_id=stay.id,
                        with_id=best.id,
                    )
                )

    scheduled = _places_from_itinerary(itinerary, places)
    paid = [
        place
        for place in scheduled
        if place.price_aed and place.price_aed.max_aed > CHEAP_PLACE_AED
    ]
    cheap_pool = [
        place
        for place in places.values()
        if place.operational_status == "open"
        and place.price_aed is not None
        and place.price_aed.max_aed <= CHEAP_PLACE_AED
    ]
    for place in paid:
        neighbours = {place.area, neighbour_area(place.area)}
        options = [row for row in cheap_pool if row.area in neighbours]
        if not options:
            options = cheap_pool
        if not options:
            break
        pick = options[0]
        savings = round(place.price_aed.max_aed * constraints.travelers, 2)
        alts.append(
            Alternative(
                kind="paid_to_free",
                description=(
                    f"Swap {place.name} for {pick.name} "
                    f"(max AED {pick.price_aed.max_aed:g})"
                ),
                savings_aed=savings,
                new_total_aed=round(max(0.0, total - savings), 2),
                replaces_id=place.id,
                with_id=pick.id,
            )
        )
        break

    for day in itinerary.days:
        for leg in day.legs:
            if leg.mode != "taxi":
                continue
            origin = places.get(leg.from_id)
            dest = places.get(leg.to_id)
            if origin is None or dest is None or graph is None:
                metro_guess = 5.0
            else:
                alt_leg = route_leg(origin, dest, graph, fares, prefer="metro")
                metro_guess = alt_leg.cost_aed or 5.0
                if alt_leg.mode == "taxi":
                    continue
            taxi_cost = (leg.cost_aed or 0) * constraints.travelers
            savings = round(taxi_cost - metro_guess * constraints.travelers, 2)
            if savings <= 0:
                continue
            alts.append(
                Alternative(
                    kind="taxi_to_metro",
                    description=f"Replace taxi {leg.from_id} → {leg.to_id} with Metro/tram",
                    savings_aed=savings,
                    new_total_aed=round(max(0.0, total - savings), 2),
                    replaces_id=f"{leg.from_id}->{leg.to_id}",
                    with_id="metro",
                )
            )
            break
        else:
            continue
        break

    meal_slots = [
        slot
        for day in itinerary.days
        for slot in day.slots
        if slot.kind == "meal" and slot.place_id
    ]
    for slot in meal_slots:
        current = restaurants.get(slot.place_id or "")
        if current is None or current.price_band not in FOOD_TIER_BELOW:
            continue
        lower_band = FOOD_TIER_BELOW[current.price_band]
        options = [
            row
            for row in restaurants.values()
            if row.area == current.area and row.price_band == lower_band
        ]
        if not options:
            continue
        pick = options[0]
        high = food_band(bands, current.price_band)
        low = food_band(bands, pick.price_band)
        if high is None or low is None:
            continue
        savings = round(
            (midpoint(high.min_aed, high.max_aed) - midpoint(low.min_aed, low.max_aed))
            * constraints.travelers,
            2,
        )
        if savings <= 0:
            continue
        alts.append(
            Alternative(
                kind="cheaper_dinner",
                description=f"Dine at {pick.name} ({pick.price_band}) instead of {current.name}",
                savings_aed=savings,
                new_total_aed=round(max(0.0, total - savings), 2),
                replaces_id=current.id,
                with_id=pick.id,
            )
        )
        break

    if constraints.budget_aed is not None and constraints.budget_aed < floor_aed:
        alts.insert(
            0,
            Alternative(
                kind="other",
                description=(
                    f"Requested budget AED {constraints.budget_aed:g} is below the "
                    f"hotel floor of AED {floor_aed:g} "
                    f"({nights_for(constraints)} {season} nights plus food and buffer)"
                ),
                savings_aed=0,
                new_total_aed=floor_aed,
                replaces_id=None,
                with_id=None,
            ),
        )
    return alts
