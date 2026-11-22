"""Preliminary stay and transport, then a deterministic sequence of the shortlist."""

from datetime import time, timedelta

from travel_planner.data.areas import stay_area
from travel_planner.data.providers.attribution import OSM_ODBL
from travel_planner.graph.context import NodeContext
from travel_planner.graph.demo import force_flag
from travel_planner.graph.schemas import SequenceDraft, StayPick
from travel_planner.graph.shortlist import food_band_for, meals_for_places
from travel_planner.graph.turn import ask, llm_active, theme_allowed, with_tokens
from travel_planner.models import Holiday, Itinerary, Slot, StayOption
from travel_planner.rules.budget import season_for
from travel_planner.rules.sequencing import group_by_day, sequence_itinerary
from travel_planner.state import TripState

_FUTURE_MUSEUM = "place-museum-of-the-future"
_EID_MUSEUM = "place-dubai-museum"
_NATIONAL_BEACH = "place-jumeirah-public-beach"


def logistics_prelim(state: TripState, ctx: NodeContext) -> dict[str, object]:
    packed = _prelim_stub(state, ctx)
    if not llm_active("logistics_prelim", ctx):
        return packed
    return _prelim_with_model(state, ctx, packed)


def _prelim_stub(state: TripState, ctx: NodeContext) -> dict[str, object]:
    constraints = state["constraints"]
    assert constraints is not None
    brief = state["plan_brief"]
    area = "Old Dubai"
    if brief is not None and brief.days and brief.days[0].areas:
        area = brief.days[0].areas[0]
    area = stay_area(area)
    tier = constraints.hotel_tier or "budget"
    hotels = ctx.tools.search_hotels(area=area, tier=tier).data
    if not hotels:
        hotels = ctx.tools.search_hotels(tier=tier).data
    season = season_for(constraints.start_date)
    flag = force_flag(state["raw_request"])

    def sort_key(hotel):
        stay = hotel.stay_option(season)
        nightly = (stay.nightly_min_aed + stay.nightly_max_aed) / 2
        if flag == "budget":
            return (-nightly,)
        metro_last = 0 if hotel.metro_nearby else 1
        return (metro_last, nightly)

    stays: list[StayOption] = [hotel.stay_option(season) for hotel in sorted(hotels, key=sort_key)]
    transport = ctx.tools.get_transport_options().data
    picked = stays[0].name if stays else "none"
    return {
        "stay_options": stays,
        "transport_options": transport,
        "_summary": f"Stay {picked}; {len(transport)} transport options.",
        "_delta": {
            "stay_id": stays[0].id if stays else None,
            "transport": [option.mode for option in transport],
        },
    }


def logistics_sequence(state: TripState, ctx: NodeContext) -> dict[str, object]:
    constraints = state["constraints"]
    candidates = state["candidates"]
    assert constraints is not None and candidates is not None
    stay = state["stay_options"][0] if state["stay_options"] else None
    start = constraints.start_date
    holidays: list[Holiday] = []
    climate = None
    notes: list[str] = []
    if start is not None:
        end = start + timedelta(days=constraints.days - 1)
        holidays = ctx.tools.holiday_lookup(start, end).data
        weather = ctx.tools.get_weather(start.month, on=start)
        climate = weather.data
        if weather.provenance == "api":
            notes.append(f"Weather: {weather.source}")
        elif weather.degraded:
            notes.append("Weather forecast unavailable; using the monthly climate table.")
    excluded = set(state["excluded_ids"])
    places = [place for place in candidates.places if place.id not in excluded]
    tie_rank = None
    if llm_active("logistics_sequence", ctx):
        tie_rank, themes, outcome = _sequence_hints(state, ctx, places, constraints)
    else:
        themes, outcome = [], None
    degraded_route = False

    def resolve_leg(origin, dest, when):
        nonlocal degraded_route
        result = ctx.tools.route_between(origin.id, dest.id, when=when)
        degraded_route = degraded_route or result.degraded
        return result.data

    meal_rows = meals_for_places(
        places,
        [row for row in candidates.restaurants if row.id not in excluded],
        ctx.tools.restaurants,
        price_band=food_band_for(constraints.hotel_tier),
    )
    itinerary = sequence_itinerary(
        places,
        meal_rows,
        constraints,
        stay=stay,
        holidays=holidays,
        climate=climate,
        stations=ctx.tools.stations,
        edges=ctx.tools.edges,
        fares=ctx.tools.fares,
        place_pool=places,
        tie_rank=tie_rank,
        resolve_leg=resolve_leg,
    )
    itinerary = _apply_themes(itinerary, themes, constraints, holidays)
    injected = _inject_demo_conflict(itinerary, state)
    if degraded_route:
        notes.append(
            "Live routing unavailable; using the Metro and tram graph or straight-line estimates."
        )
    elif any(leg.provenance == "api" for day in itinerary.days for leg in day.legs):
        notes.append(f"Road durations: {OSM_ODBL}.")
    payload: dict[str, object] = {
        "draft_itinerary": itinerary,
        "_summary": f"{len(itinerary.days)} days sequenced"
        + (f"; injected {injected}." if injected else "."),
        "_delta": {
            "days": len(itinerary.days),
            "stay_id": stay.id if stay else None,
            "injected": injected,
        },
    }
    if notes:
        payload["warnings"] = notes
    if outcome is not None:
        return with_tokens(outcome, payload)
    return payload


def _inject_demo_conflict(itinerary: Itinerary, state: TripState) -> str | None:
    """Schedule one catalog conflict the stub 'LLM' ignored, once, until revise excludes it."""

    flag = force_flag(state["raw_request"])
    excluded = set(state["excluded_ids"])
    if not itinerary.days or flag not in {"museum", "eid", "national"}:
        return None
    target = {
        "museum": _FUTURE_MUSEUM,
        "eid": _EID_MUSEUM,
        "national": _NATIONAL_BEACH,
    }[flag]
    if target in excluded or _scheduled(itinerary, target):
        return None
    note = {
        "museum": "Demo stub scheduled a reopening venue.",
        "eid": "Demo stub scheduled a heritage venue on Eid day one.",
        "national": "Demo stub scheduled a beach on a high-crowd holiday.",
    }[flag]
    end = time(10, 30) if flag != "national" else time(11, 0)
    itinerary.days[0].slots.insert(
        0,
        Slot(
            start=time(10, 0),
            end=end,
            place_id=target,
            kind="activity",
            notes=note,
        ),
    )
    return target


def _scheduled(itinerary: Itinerary, place_id: str) -> bool:
    return any(
        slot.place_id == place_id and slot.kind == "activity"
        for day in itinerary.days
        for slot in day.slots
    )


def _prelim_with_model(
    state: TripState,
    ctx: NodeContext,
    packed: dict[str, object],
) -> dict[str, object]:
    stays = packed["stay_options"]
    assert isinstance(stays, list)
    if not stays:
        return packed
    lines = [
        f"{stay.id} | {stay.name} | {stay.area} | tier={stay.tier} | metro={stay.metro_nearby}"
        for stay in stays[:8]
    ]
    data = "hotel_shortlist:\n" + "\n".join(lines)

    def fallback() -> StayPick:
        return StayPick(hotel_id=stays[0].id)

    def check(pick: StayPick) -> str | None:
        if pick.hotel_id not in {stay.id for stay in stays}:
            return "hotel_id must come from hotel_shortlist"
        return None

    outcome = ask("logistics_prelim", StayPick, data, ctx, fallback, check=check)
    ordered = sorted(stays, key=lambda stay: 0 if stay.id == outcome.value.hotel_id else 1)
    payload = {
        **packed,
        "stay_options": ordered,
        "_summary": (
            f"Stay {ordered[0].name}; {len(packed['transport_options'])} transport options."
        ),
        "_delta": {
            "stay_id": ordered[0].id,
            "transport": [option.mode for option in packed["transport_options"]],
        },
    }
    return with_tokens(outcome, payload)


def _sequence_hints(state, ctx, places, constraints):
    clusters = group_by_day(places, constraints.days, pool=places)
    lines = []
    for index, cluster in enumerate(clusters, start=1):
        ids = ", ".join(place.id for place in cluster) or "(empty)"
        lines.append(f"day {index}: {ids}")
    data = "clusters:\n" + "\n".join(lines)

    def fallback() -> SequenceDraft:
        return SequenceDraft(themes=[], place_order=[])

    def check(draft: SequenceDraft) -> str | None:
        if draft.themes and len(draft.themes) != constraints.days:
            return f"themes must contain {constraints.days} strings"
        for index, theme in enumerate(draft.themes, start=1):
            if not theme_allowed(theme, index, constraints, ctx.tools.holidays):
                return f"theme {index} conflicts with the holiday calendar"
        return None

    outcome = ask("logistics_sequence", SequenceDraft, data, ctx, fallback, check=check)
    rank = {place_id: index for index, place_id in enumerate(outcome.value.place_order)}
    return rank or None, list(outcome.value.themes), outcome


def _apply_themes(itinerary, themes, constraints, holidays):
    if len(themes) != len(itinerary.days):
        return itinerary
    if any(
        not theme_allowed(theme, day.day, constraints, holidays)
        for day, theme in zip(itinerary.days, themes, strict=True)
    ):
        return itinerary
    days = [
        day.model_copy(update={"theme": theme})
        for day, theme in zip(itinerary.days, themes, strict=True)
    ]
    return itinerary.model_copy(update={"days": days})
