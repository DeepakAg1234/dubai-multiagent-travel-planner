"""Deterministic shortlists. The LLM may only pick ids from these lists."""

from __future__ import annotations

from travel_planner.data.areas import PLANNING_AREAS, neighbour_area, stay_area
from travel_planner.models import Constraints, Place, Restaurant

INTEREST_TAGS: dict[str, set[str]] = {
    "culture": {"culture"},
    "beaches": {"beach"},
    "beach": {"beach"},
    "family": {"family"},
    "nightlife": {"nightlife"},
    "landmark": {"landmark"},
    "shopping": {"shopping"},
    "outdoor": {"outdoor"},
}

FOOD_BAND = {"budget": "budget", "mid": "mid", "luxury": "upscale"}
PLACE_LIMIT = 12
RESTAURANT_LIMIT = 8


def food_band_for(hotel_tier: str | None) -> str:
    return FOOD_BAND.get(hotel_tier or "budget", "budget")


def meals_for_places(
    places: list[Place],
    picked: list[Restaurant],
    catalog: list[Restaurant],
    *,
    price_band: str,
) -> list[Restaurant]:
    """Keep the chosen meals and add catalog rows for each place's area.

    A model can pick an Al Quoz place and only Old Dubai restaurants. Sequencing
    then has nothing to serve on that day. The neighbour on the same Metro line
    is included, which is where thin areas already borrow a hotel.
    """

    rows = list(picked)
    seen = {row.id for row in rows}
    areas: list[str] = []
    for place in places:
        host = stay_area(place.area)
        for area in (host, neighbour_area(host)):
            if area not in areas:
                areas.append(area)
    for row in catalog:
        if row.id in seen or row.area not in areas or row.price_band != price_band:
            continue
        if row.area not in PLANNING_AREAS:
            continue
        rows.append(row)
        seen.add(row.id)
    return rows


def score_place(
    place: Place,
    constraints: Constraints,
    *,
    hot: bool,
) -> float | None:
    """Higher is better. Closed and reopening places are not scored."""

    if place.operational_status != "open":
        return None
    score = 1.0
    interests = {item.lower() for item in constraints.interests}
    wanted: set[str] = set()
    for interest in interests:
        wanted |= INTEREST_TAGS.get(interest, set())
    tags = set(place.tags)
    if wanted and tags & wanted:
        score += 5
    if "family" in interests and "family" in tags:
        score += 4
    if constraints.avoid_crowds:
        if place.crowd_level == "high":
            score -= 4
        elif place.crowd_level == "low":
            score += 2
    if hot and place.indoor is False:
        score -= 3
    elif hot and place.indoor is True:
        score += 2
    return score


def shortlist_places(
    places: list[Place],
    constraints: Constraints,
    excluded: set[str],
    *,
    hot: bool,
    limit: int = PLACE_LIMIT,
) -> list[Place]:
    ranked: list[tuple[float, Place]] = []
    for place in places:
        if place.id in excluded:
            continue
        score = score_place(place, constraints, hot=hot)
        if score is None:
            continue
        if place.area in {"Business Bay", "Al Quoz", "Dubai Creek"}:
            score += 0.25
        ranked.append((score, place))
    ranked.sort(key=lambda item: (-item[0], item[1].name))
    chosen = [place for _, place in ranked[:limit]]
    if any(item.lower() == "family" for item in constraints.interests):
        seen = {place.id for place in chosen}
        for place in places:
            if place.id in seen or place.id in excluded:
                continue
            if "family" in place.tags and place.operational_status == "open":
                chosen.append(place)
                seen.add(place.id)
    return chosen


def shortlist_restaurants(
    restaurants: list[Restaurant],
    areas: list[str],
    *,
    price_band: str,
    limit: int = RESTAURANT_LIMIT,
) -> list[Restaurant]:
    """Planning-area meals only. Thin areas also take the Metro neighbour."""

    wanted: list[str] = []
    for area in areas:
        host = stay_area(area)
        if host not in wanted:
            wanted.append(host)
        neighbour = neighbour_area(host)
        if neighbour not in wanted:
            wanted.append(neighbour)
    if not wanted:
        wanted = list(PLANNING_AREAS[:2])
    rows = [
        row
        for row in restaurants
        if row.area in wanted and row.price_band == price_band and row.area in PLANNING_AREAS
    ]
    return rows[:limit]


def gate_places(picked: list[str], shortlist: list[Place]) -> list[str]:
    """Drop invented ids and any closed or reopening row, even if it was listed."""

    by_id = {place.id: place for place in shortlist}
    kept: list[str] = []
    for place_id in picked:
        place = by_id.get(place_id)
        if place is None or place.operational_status != "open":
            continue
        if place_id not in kept:
            kept.append(place_id)
    return kept


def gate_restaurants(picked: list[str], shortlist: list[Restaurant]) -> list[str]:
    by_id = {row.id: row for row in shortlist}
    kept: list[str] = []
    for restaurant_id in picked:
        row = by_id.get(restaurant_id)
        if row is None or row.area not in PLANNING_AREAS:
            continue
        if restaurant_id not in kept:
            kept.append(restaurant_id)
    return kept
