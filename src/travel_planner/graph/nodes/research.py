"""Destination research. The stub stays when Groq is off; otherwise the model picks a shortlist."""

from datetime import time, timedelta

from travel_planner.data.areas import PLANNING_AREAS, neighbour_area, stay_area
from travel_planner.data.providers.attribution import OSM_ODBL
from travel_planner.graph.context import NodeContext
from travel_planner.graph.demo import named_planning_areas
from travel_planner.graph.schemas import ResearchPick
from travel_planner.graph.shortlist import (
    food_band_for,
    gate_places,
    gate_restaurants,
    shortlist_places,
    shortlist_restaurants,
)
from travel_planner.graph.turn import ask, llm_active, untrusted, with_tokens
from travel_planner.models import Candidates, Place, Restaurant
from travel_planner.rules.holidays import CROWD_CATEGORIES, HERITAGE_CATEGORIES, effects_on
from travel_planner.rules.hours import parse_window
from travel_planner.state import TripState

# Fixed shortlist the stub prefers when the row is still eligible.
_PREFERRED = (
    "place-al-fahidi-historical-neighbourhood",
    "place-jumeirah-public-beach",
    "place-dubai-museum",
)
_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_LUNCH = time(12, 30)
_DINNER = time(19, 30)


def destination_research(state: TripState, ctx: NodeContext) -> dict[str, object]:
    if llm_active("destination_research", ctx):
        return _research_with_model(state, ctx)
    return _research_stub(state, ctx)


def _research_stub(state: TripState, ctx: NodeContext) -> dict[str, object]:
    constraints = state["constraints"]
    assert constraints is not None
    excluded = set(state["excluded_ids"])
    holidays = ctx.tools.holidays
    places = _select_places(
        ctx,
        constraints,
        excluded,
        holidays,
        focus=named_planning_areas(state["raw_request"]),
    )
    areas = list(dict.fromkeys(place.area for place in places))
    restaurants, meal_note = _select_restaurants(ctx, areas)
    candidates = Candidates(places=places, restaurants=restaurants, areas=areas)
    payload: dict[str, object] = {
        "candidates": candidates,
        "_summary": (
            f"{len(places)} places and {len(restaurants)} restaurants "
            f"in {', '.join(areas) or 'no area'}."
        ),
        "_delta": {
            "place_ids": [place.id for place in places],
            "restaurant_ids": [row.id for row in restaurants],
            "areas": areas,
        },
    }
    if meal_note:
        payload["warnings"] = [meal_note]
    return payload


def _select_places(
    ctx: NodeContext,
    constraints,
    excluded: set[str],
    holidays,
    *,
    focus: list[str] | None = None,
) -> list[Place]:
    chosen: list[Place] = []
    seen: set[str] = set()
    if focus:
        wanted = set(focus)
        for place in ctx.tools.places:
            if place.area not in wanted:
                continue
            if not _eligible(place, constraints, excluded, holidays):
                continue
            chosen.append(place)
            seen.add(place.id)
            if len(chosen) >= constraints.days:
                return chosen
    for place_id in _PREFERRED:
        preferred = ctx.tools.get_place(place_id)
        if preferred is not None and _eligible(preferred, constraints, excluded, holidays):
            chosen.append(preferred)
            seen.add(preferred.id)
    if len(chosen) < constraints.days:
        family = any(item.lower() == "family" for item in constraints.interests)
        for place in ctx.tools.places:
            if place.id in seen:
                continue
            if not family and place.area not in PLANNING_AREAS:
                continue
            if not _eligible(place, constraints, excluded, holidays):
                continue
            chosen.append(place)
            seen.add(place.id)
            if len(chosen) >= constraints.days:
                break
    return chosen[: constraints.days]


def _eligible(place: Place, constraints, excluded: set[str], holidays) -> bool:
    if place.id in excluded or place.operational_status != "open":
        return False
    if not _opens_for_a_morning_visit(place):
        return False
    visit = place.typical_visit_minutes
    if visit is not None and visit > 120:
        return False
    if constraints.avoid_crowds and place.crowd_level == "high":
        return False
    if constraints.start_date is None:
        return True
    for offset in range(constraints.days):
        day = constraints.start_date + timedelta(days=offset)
        effects = effects_on(holidays, day)
        if effects is None:
            continue
        if effects.heritage_may_close and place.category in HERITAGE_CATEGORIES:
            return False
        if (
            effects.high_crowd
            and constraints.avoid_crowds
            and place.category in CROWD_CATEGORIES
        ):
            return False
    return True


def _opens_for_a_morning_visit(place: Place) -> bool:
    """Morning hours leave room for lunch after the visit."""

    hours = place.opening_hours or {}
    if "daily" in hours:
        windows = [parse_window(hours["daily"])]
    else:
        windows = [parse_window(hours.get(day)) for day in _WEEKDAYS]
    return all(
        window is not None and window[0] <= time(10, 0) and window[1] >= time(13, 0)
        for window in windows
    )


def _select_restaurants(
    ctx: NodeContext,
    areas: list[str],
) -> tuple[list[Restaurant], str | None]:
    chosen: list[Restaurant] = []
    enriched = False
    degraded = False
    search_areas: list[str] = []
    for area in areas:
        for host in (stay_area(area), neighbour_area(stay_area(area))):
            if host not in search_areas:
                search_areas.append(host)
    for area in search_areas:
        found = ctx.tools.search_restaurants(
            area=area,
            price_band="budget",
            meal_types=["lunch", "dinner"],
        )
        degraded = degraded or found.degraded
        open_rows = [row for row in found.data if _open_for_meals(row)]
        for row in open_rows[:4]:
            if "Overpass" in row.source:
                enriched = True
        chosen.extend(open_rows[:4])
    return chosen, _restaurant_note(enriched, degraded)


def _open_for_meals(restaurant: Restaurant) -> bool:
    hours = restaurant.opening_hours or {}
    if "daily" in hours:
        window = parse_window(hours["daily"])
        return window is not None and window[0] <= _LUNCH and window[1] >= _DINNER
    for day in _WEEKDAYS:
        window = parse_window(hours.get(day))
        if window is None or window[0] > _LUNCH or window[1] < _DINNER:
            return False
    return True


def _research_with_model(state: TripState, ctx: NodeContext) -> dict[str, object]:
    constraints = state["constraints"]
    assert constraints is not None
    excluded = set(state["excluded_ids"])
    climate = None
    if constraints.start_date is not None:
        climate = ctx.tools.get_weather(
            constraints.start_date.month,
            on=constraints.start_date,
        ).data
    hot = climate is not None and climate.avg_high_c >= 35
    places = shortlist_places(ctx.tools.places, constraints, excluded, hot=hot)
    brief = state["plan_brief"]
    areas: list[str] = []
    if brief is not None:
        for day in brief.days:
            areas.extend(day.areas)
    if not areas:
        areas = list(dict.fromkeys(place.area for place in places))
    band = food_band_for(constraints.hotel_tier)
    restaurants = shortlist_restaurants(ctx.tools.restaurants, areas, price_band=band)
    meal_note = None
    if ctx.tools.live_enabled:
        restaurants, meal_note = _with_live_restaurants(ctx, restaurants, band)
    museum = ctx.tools.get_place("place-museum-of-the-future")
    listed = list(places)
    if museum is not None and all(row.id != museum.id for row in listed):
        listed.append(museum)
    data = "\n".join(
        [
            constraints.model_dump_json(),
            "place_shortlist:",
            *[_place_line(place) for place in listed],
            "restaurant_shortlist:",
            *[_restaurant_line(row) for row in restaurants],
        ]
    )
    open_ids = [place.id for place in places]

    def fallback() -> ResearchPick:
        return ResearchPick(
            place_ids=open_ids[: max(constraints.days, 1)],
            restaurant_ids=[row.id for row in restaurants[:4]],
        )

    outcome = ask("destination_research", ResearchPick, data, ctx, fallback)
    place_ids = gate_places(outcome.value.place_ids, places)
    if not place_ids:
        place_ids = open_ids[: max(constraints.days, 1)]
    restaurant_ids = gate_restaurants(outcome.value.restaurant_ids, restaurants)
    if not restaurant_ids:
        restaurant_ids = [row.id for row in restaurants[:4]]
    by_place = {place.id: place for place in places}
    by_restaurant = {row.id: row for row in restaurants}
    chosen_places = [by_place[place_id] for place_id in place_ids if place_id in by_place]
    chosen_restaurants = [
        by_restaurant[row_id] for row_id in restaurant_ids if row_id in by_restaurant
    ]
    chosen_areas = list(dict.fromkeys(place.area for place in chosen_places))
    candidates = Candidates(
        places=chosen_places,
        restaurants=chosen_restaurants,
        areas=chosen_areas,
    )
    reasons = "; ".join(outcome.value.reasons[:3])
    summary = (
        f"{len(chosen_places)} places and {len(chosen_restaurants)} restaurants "
        f"in {', '.join(chosen_areas) or 'no area'}."
    )
    if reasons:
        summary = f"{summary} {reasons}"
    payload: dict[str, object] = {
        "candidates": candidates,
        "_summary": summary,
        "_delta": {
            "place_ids": [place.id for place in chosen_places],
            "restaurant_ids": [row.id for row in chosen_restaurants],
            "areas": chosen_areas,
        },
    }
    if meal_note:
        payload["warnings"] = [meal_note]
    return with_tokens(outcome, payload)


def _with_live_restaurants(
    ctx: NodeContext,
    restaurants: list[Restaurant],
    band: str,
) -> tuple[list[Restaurant], str | None]:
    enriched = False
    degraded = False
    merged: dict[str, Restaurant] = {}
    for area in dict.fromkeys(row.area for row in restaurants):
        found = ctx.tools.search_restaurants(area=area, price_band=band)
        degraded = degraded or found.degraded
        for row in found.data:
            merged[row.id] = row
            if "Overpass" in row.source:
                enriched = True
    ordered = [merged.get(row.id, row) for row in restaurants]
    return ordered, _restaurant_note(enriched, degraded)


def _restaurant_note(enriched: bool, degraded: bool) -> str | None:
    if enriched:
        return f"Restaurant details: {OSM_ODBL}."
    if degraded:
        return "Restaurant hours and cuisine stayed on the curated catalog."
    return None


def _place_line(place: Place) -> str:
    tags = ",".join(place.tags)
    return (
        f"{place.id} | {place.name} | {place.area} | {place.category} | tags={tags} | "
        f"crowd={place.crowd_level} | indoor={place.indoor} | status={place.operational_status} | "
        f"provenance={place.provenance}\n{untrusted(place.id, place.source)}"
    )


def _restaurant_line(row: Restaurant) -> str:
    return (
        f"{row.id} | {row.name} | {row.area} | band={row.price_band} | "
        f"meals={','.join(row.meal_types)} | provenance={row.provenance}\n"
        f"{untrusted(row.id, row.source)}"
    )
