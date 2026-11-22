"""Orchestrator. A missing Groq key keeps the holiday-aware stub brief."""

from datetime import timedelta

from travel_planner.graph.context import NodeContext
from travel_planner.graph.demo import force_flag, named_planning_areas
from travel_planner.graph.events import make_event, publish
from travel_planner.graph.schemas import ReviseDraft
from travel_planner.graph.turn import ask, brief_allowed, known_areas, llm_active, with_tokens
from travel_planner.models import DayBrief, PlanBrief
from travel_planner.rules.holidays import effects_on
from travel_planner.state import TripState

_FUTURE_MUSEUM = "place-museum-of-the-future"
_PACES = {"relaxed", "balanced", "packed"}


def orchestrator_plan(state: TripState, ctx: NodeContext) -> dict[str, object]:
    if not llm_active("orchestrator_plan", ctx):
        return _plan_stub(state, ctx)
    return _plan_with_model(state, ctx)


def _plan_stub(state: TripState, ctx: NodeContext) -> dict[str, object]:
    constraints = state["constraints"]
    assert constraints is not None
    holidays = ctx.tools.holidays
    areas = named_planning_areas(state["raw_request"]) or _areas_for(constraints.interests)
    days: list[DayBrief] = []
    for index in range(1, constraints.days + 1):
        area = areas[(index - 1) % len(areas)]
        when = None
        if constraints.start_date is not None:
            when = constraints.start_date + timedelta(days=index - 1)
        effects = effects_on(holidays, when) if when else None
        theme = f"Day {index} {area}"
        hints: list[str] = []
        if area == "Old Dubai":
            theme = f"Day {index} Old Dubai culture"
        elif area == "Jumeirah":
            theme = f"Day {index} Jumeirah beach"
        if effects and effects.heritage_may_close and area == "Old Dubai":
            theme = f"Day {index} Old Dubai neighbourhood"
            hints.append("Eid day one: skip museums, mosques, and galleries.")
        if (
            effects
            and effects.high_crowd
            and constraints.avoid_crowds
            and area == "Jumeirah"
        ):
            area = "Old Dubai"
            theme = f"Day {index} Old Dubai indoors"
            hints.append("National Day crowds: no beach or mall day.")
        if constraints.avoid_crowds:
            hints.append("Prefer low and medium crowd places.")
        days.append(DayBrief(day=index, theme=theme, areas=[area], crowd_hints=hints))
    notes = [
        "Cuisine focus is empty because every restaurant cuisine is unspecified.",
    ]
    flag = force_flag(state["raw_request"])
    if flag:
        notes.append(f"force:{flag}")
    brief = PlanBrief(days=days, cuisine_focus=[], notes=notes)
    return {
        "plan_brief": brief,
        "_summary": "; ".join(day.theme for day in days),
        "_delta": {"days": [day.theme for day in days]},
    }


def orchestrator_revise(state: TripState, ctx: NodeContext) -> dict[str, object]:
    fresh, summary, count = _revise_stub_decision(state, ctx)
    if llm_active("orchestrator_revise", ctx):
        return _revise_with_model(state, ctx, fresh, summary, count)
    return _revise_payload(state, fresh, summary, count)


def _revise_stub_decision(
    state: TripState,
    ctx: NodeContext,
) -> tuple[list[str], str, int]:
    report = state["review_report"]
    assert report is not None
    itinerary = state["draft_itinerary"]
    scheduled: list[str] = []
    if itinerary is not None:
        scheduled = [
            slot.place_id
            for day in itinerary.days
            for slot in day.slots
            if slot.place_id
        ]
    already = set(state["excluded_ids"])
    blockers = [row for row in report.violations if row.severity == "blocker"]
    detail = " ".join(row.detail for row in blockers)
    fresh: list[str] = []
    for place_id in scheduled:
        if place_id in already or place_id in fresh:
            continue
        if place_id == _FUTURE_MUSEUM and "Museum of the Future" in detail:
            fresh.append(place_id)
            continue
        place = ctx.tools.get_place(place_id)
        if place is not None and any(row.rule == "operational_status" for row in blockers):
            if place.operational_status != "open":
                fresh.append(place_id)
                continue
        named = place.name if place is not None else ""
        if not named:
            restaurant = ctx.tools.get_restaurant(place_id)
            named = restaurant.name if restaurant is not None else ""
        if named and named in detail:
            fresh.append(place_id)
    count = int(state["revision_count"]) + 1
    summary = (
        f"Revision {count}: excluded {', '.join(fresh)}"
        if fresh
        else f"Revision {count}: plan blockers remain."
    )
    return fresh, summary, count


def _revise_payload(
    state: TripState,
    fresh: list[str],
    summary: str,
    count: int,
    *,
    tokens: dict[str, int] | None = None,
    pace: str | None = None,
) -> dict[str, object]:
    event = make_event(
        "orchestrator_revise",
        "revision",
        summary,
        {"excluded_ids": fresh, "revision_count": count},
    )
    publish(event)
    brief = state["plan_brief"]
    notes = list(brief.notes) if brief is not None else []
    notes.append(summary)
    updated = brief.model_copy(update={"notes": notes}) if brief is not None else None
    payload: dict[str, object] = {
        "plan_brief": updated,
        "excluded_ids": fresh,
        "revision_count": count,
        "events": [event],
        "_summary": summary,
        "_delta": {"excluded_ids": fresh, "revision_count": count},
    }
    if pace in _PACES and state["constraints"] is not None:
        payload["constraints"] = state["constraints"].model_copy(update={"pace": pace})
    if tokens is not None:
        payload["_tokens"] = tokens
    return payload


def _plan_with_model(state: TripState, ctx: NodeContext) -> dict[str, object]:
    constraints = state["constraints"]
    assert constraints is not None
    areas = known_areas(ctx.tools.places)
    allowed = set(areas)
    holiday_lines = []
    if constraints.start_date is not None:
        for index in range(constraints.days):
            day = constraints.start_date + timedelta(days=index)
            effects = effects_on(ctx.tools.holidays, day)
            if effects is not None:
                holiday_lines.append(f"Day {index + 1} {day.isoformat()}: {effects.note()}")
    data = "\n".join(
        [
            constraints.model_dump_json(),
            "allowed_areas: " + ", ".join(areas),
            "holiday_notes:",
            *holiday_lines,
        ]
    )

    def fallback() -> PlanBrief:
        stub = _plan_stub(state, ctx)
        brief = stub["plan_brief"]
        assert isinstance(brief, PlanBrief)
        return brief

    def check(brief: PlanBrief) -> str | None:
        return brief_allowed(brief, constraints, ctx.tools.holidays, allowed)

    outcome = ask("orchestrator_plan", PlanBrief, data, ctx, fallback, check=check)
    brief = outcome.value
    if brief_allowed(brief, constraints, ctx.tools.holidays, allowed):
        brief = fallback()
    return with_tokens(
        outcome,
        {
            "plan_brief": brief,
            "_summary": "; ".join(day.theme for day in brief.days),
            "_delta": {"days": [day.theme for day in brief.days]},
        },
    )


def _revise_with_model(
    state: TripState,
    ctx: NodeContext,
    fresh: list[str],
    summary: str,
    count: int,
) -> dict[str, object]:
    itinerary = state["draft_itinerary"]
    scheduled = []
    if itinerary is not None:
        scheduled = [
            slot.place_id
            for day in itinerary.days
            for slot in day.slots
            if slot.place_id
        ]
    scheduled_set = set(scheduled)
    report = state["review_report"]
    assert report is not None
    data = "\n".join(
        [
            "scheduled_ids: " + ", ".join(scheduled),
            report.model_dump_json(),
        ]
    )

    def fallback() -> ReviseDraft:
        return ReviseDraft(excluded_ids=list(fresh), notes=[summary])

    def check(draft: ReviseDraft) -> str | None:
        unknown = [item for item in draft.excluded_ids if item not in scheduled_set]
        if unknown:
            return "excluded_ids must be scheduled catalog ids"
        if draft.pace not in {None, "", *_PACES}:
            return "pace must be relaxed, balanced, packed, or null"
        return None

    outcome = ask("orchestrator_revise", ReviseDraft, data, ctx, fallback, check=check)
    already = set(state["excluded_ids"])
    chosen = [
        item
        for item in dict.fromkeys([*fresh, *outcome.value.excluded_ids])
        if item in scheduled_set and item not in already
    ]
    pace = outcome.value.pace if outcome.value.pace in _PACES else None
    note = summary
    if outcome.value.notes:
        note = f"{summary} {outcome.value.notes[0]}"
    return _revise_payload(state, chosen, note, count, tokens=outcome.tokens(), pace=pace)


def _areas_for(interests: list[str]) -> list[str]:
    areas: list[str] = []
    lowered = {item.lower() for item in interests}
    if "culture" in lowered or not lowered:
        areas.append("Old Dubai")
    if "beaches" in lowered or "beach" in lowered:
        areas.append("Jumeirah")
    if "landmark" in lowered:
        areas.append("Downtown")
    if "family" in lowered or "nightlife" in lowered:
        areas.append("Marina / JBR")
    if not areas:
        areas.append("Old Dubai")
    return areas
