"""Deterministic budget, then one catalog alternative per revision."""

from datetime import timedelta

from travel_planner.graph.context import NodeContext
from travel_planner.graph.events import make_event, publish
from travel_planner.graph.schemas import AdjustChoice, BudgetNarration
from travel_planner.graph.turn import ask, llm_active, with_tokens
from travel_planner.models import Alternative, Itinerary
from travel_planner.rules.budget import compute_budget, season_for
from travel_planner.rules.fares import TransitGraph
from travel_planner.rules.holidays import effects_on
from travel_planner.state import TripState


def budget(state: TripState, ctx: NodeContext) -> dict[str, object]:
    constraints = state["constraints"]
    itinerary = state["draft_itinerary"]
    assert constraints is not None and itinerary is not None
    places = {row.id: row for row in ctx.tools.places}
    restaurants = {row.id: row for row in ctx.tools.restaurants}
    report = compute_budget(
        itinerary,
        constraints,
        places=places,
        restaurants=restaurants,
        hotels=ctx.tools.hotels,
        bands=ctx.tools.bands,
        fares=ctx.tools.fares,
        buffer_pct=ctx.settings.buffer_pct,
        drop_lunch_days=_drop_lunch_days(state, ctx),
        graph=TransitGraph(ctx.tools.stations, ctx.tools.edges),
    )
    summary = (
        f"AED {report.total_aed:g} "
        f"{'within' if report.within_budget else 'over'} budget."
    )
    payload: dict[str, object] = {
        "budget_report": report,
        "_summary": summary,
        "_delta": {
            "total_aed": report.total_aed,
            "within_budget": report.within_budget,
            "alternatives": len(report.alternatives),
        },
    }
    if not llm_active("budget", ctx):
        return payload
    narration = _narrate(report, ctx)
    if narration.value.summary:
        payload["_summary"] = f"{summary} {narration.value.summary}"
    return with_tokens(narration, payload)


def budget_adjust(state: TripState, ctx: NodeContext) -> dict[str, object]:
    report = state["budget_report"]
    itinerary = state["draft_itinerary"]
    constraints = state["constraints"]
    assert report is not None and itinerary is not None and constraints is not None
    budget_aed = constraints.budget_aed
    chosen = _choose_alternative(report, budget_aed, ctx)
    updated, applied = (
        _apply(itinerary, chosen, ctx, constraints) if chosen is not None else (itinerary, False)
    )
    count = int(state["revision_count"]) + 1
    if applied and chosen is not None:
        summary = f"Revision {count}: {chosen.description}"
    else:
        summary = f"Revision {count}: no priced alternative could close the gap."
    event = make_event(
        "budget_adjust",
        "revision",
        summary,
        {"revision_count": count, "alternative": chosen.kind if chosen else None},
    )
    publish(event)
    warnings = [] if applied else [summary]
    return {
        "draft_itinerary": updated,
        "revision_count": count,
        "warnings": warnings,
        "events": [event],
        "_summary": summary,
        "_delta": {"revision_count": count, "applied": applied},
    }


def _deterministic_alternative(report, budget_aed: float | None) -> Alternative | None:
    return next(
        (
            alt
            for alt in report.alternatives
            if alt.savings_aed > 0
            and alt.with_id
            and alt.kind != "other"
            and (budget_aed is None or alt.new_total_aed <= budget_aed)
        ),
        None,
    )


def _choose_alternative(report, budget_aed: float | None, ctx: NodeContext) -> Alternative | None:
    fallback_choice = _deterministic_alternative(report, budget_aed)
    if not llm_active("budget_adjust", ctx) or not report.alternatives:
        return fallback_choice
    lines = [
        (
            f"{alt.kind} | replaces={alt.replaces_id} | with={alt.with_id} | "
            f"savings={alt.savings_aed:g} | new_total={alt.new_total_aed:g} | {alt.description}"
        )
        for alt in report.alternatives
    ]
    data = f"budget_aed={budget_aed}\n" + "\n".join(lines)

    def fallback() -> AdjustChoice:
        if fallback_choice is None:
            return AdjustChoice()
        return AdjustChoice(
            kind=fallback_choice.kind,
            with_id=fallback_choice.with_id,
            replaces_id=fallback_choice.replaces_id,
        )

    outcome = ask("budget_adjust", AdjustChoice, data, ctx, fallback)
    match = next(
        (
            alt
            for alt in report.alternatives
            if alt.kind == outcome.value.kind
            and alt.with_id == outcome.value.with_id
            and alt.savings_aed > 0
            and (budget_aed is None or alt.new_total_aed <= budget_aed)
        ),
        None,
    )
    return match or fallback_choice


def _narrate(report, ctx: NodeContext):
    data = report.model_dump_json()

    def fallback() -> BudgetNarration:
        return BudgetNarration(
            summary="Figures follow the catalog and are estimated unless a line is verified.",
        )

    return ask("budget", BudgetNarration, data, ctx, fallback)


def _drop_lunch_days(state: TripState, ctx: NodeContext) -> int:
    constraints = state["constraints"]
    if constraints is None or constraints.start_date is None:
        return 0
    count = 0
    for offset in range(constraints.days):
        day = constraints.start_date + timedelta(days=offset)
        effects = effects_on(ctx.tools.holidays, day)
        if effects is not None and effects.drop_lunch:
            count += 1
    return count


def _apply(
    itinerary: Itinerary,
    alt: Alternative,
    ctx: NodeContext,
    constraints,
) -> tuple[Itinerary, bool]:
    updated = itinerary.model_copy(deep=True)
    if alt.kind == "cheaper_hotel" and alt.with_id:
        hotel = ctx.tools.get_hotel(alt.with_id)
        if hotel is None:
            return itinerary, False
        new_stay = hotel.stay_option(season_for(constraints.start_date))
        old_id = updated.stay.id if updated.stay else None
        updated.stay = new_stay
        if old_id:
            for day in updated.days:
                for slot in day.slots:
                    if slot.place_id == old_id:
                        slot.place_id = new_stay.id
        return updated, True
    if alt.kind in {"paid_to_free", "cheaper_dinner"} and alt.replaces_id and alt.with_id:
        changed = False
        for day in updated.days:
            for slot in day.slots:
                if slot.place_id == alt.replaces_id:
                    slot.place_id = alt.with_id
                    changed = True
        return (updated, True) if changed else (itinerary, False)
    if alt.kind == "taxi_to_metro" and alt.replaces_id and "->" in alt.replaces_id:
        origin, _, dest = alt.replaces_id.partition("->")
        changed = False
        for day in updated.days:
            legs = []
            for leg in day.legs:
                if leg.mode == "taxi" and leg.from_id == origin and leg.to_id == dest:
                    legs.append(leg.model_copy(update={"mode": "metro", "cost_aed": None}))
                    changed = True
                else:
                    legs.append(leg)
            day.legs = legs
        return (updated, True) if changed else (itinerary, False)
    return itinerary, False
