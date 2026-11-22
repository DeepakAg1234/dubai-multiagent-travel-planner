"""Assemble the itinerary the API returns, with a provenance narrative."""

from travel_planner.graph.context import NodeContext
from travel_planner.graph.schemas import FinalNarrative
from travel_planner.graph.turn import ask, llm_active, provenance_lines, with_tokens
from travel_planner.state import TripState


def finalize(state: TripState, ctx: NodeContext) -> dict[str, object]:
    itinerary = state["draft_itinerary"]
    assert itinerary is not None
    report = state["review_report"]
    existing = list(state["warnings"])
    extra: list[str] = []
    if report is not None and not report.passed:
        for violation in report.violations:
            if violation.severity != "blocker":
                continue
            line = f"{violation.rule}: {violation.detail}"
            if line not in existing and line not in extra:
                extra.append(line)
    history = [event.summary for event in state["events"] if event.phase == "revision"]
    provenance: dict[str, float] = {}
    budget = state["budget_report"]
    if budget is not None:
        for line in budget.lines:
            provenance[line.provenance] = round(
                provenance.get(line.provenance, 0.0) + line.total_aed,
                2,
            )
    callouts = provenance_lines(
        ctx.tools.places,
        [station.provenance for station in ctx.tools.stations],
    )
    assumptions = list(state["assumptions"])
    for line in callouts:
        if line not in assumptions:
            assumptions.append(line)
    narrative, outcome = _narrative(state, ctx, callouts, history)
    final = itinerary.model_copy(
        update={
            "budget": budget,
            "provenance_summary": provenance,
            "assumptions": assumptions,
            "warnings": existing + extra,
            "revision_history": history,
            "narrative": narrative,
        }
    )
    passed = bool(report.passed) if report is not None else False
    payload: dict[str, object] = {
        "final_itinerary": final,
        "warnings": extra,
        "_summary": "Finalized." if passed else "Finalized with warnings.",
        "_delta": {
            "passed": passed,
            "warnings": len(final.warnings),
            "revisions": len(history),
        },
    }
    if outcome is None:
        return payload
    return with_tokens(outcome, payload)


def _narrative(state: TripState, ctx: NodeContext, callouts: list[str], history: list[str]):
    holiday_notes = [
        day.holiday_note
        for day in (state["draft_itinerary"].days if state["draft_itinerary"] else [])
        if day.holiday_note
    ]
    base = " ".join(callouts)
    if holiday_notes:
        base = f"{base} Holiday notes: {' '.join(holiday_notes)}"
    if not llm_active("finalize", ctx):
        return base, None
    data = "\n".join(
        [
            *callouts,
            f"revisions: {len(history)}",
            *holiday_notes,
            f"assumptions: {state['assumptions']}",
            f"warnings: {state['warnings']}",
        ]
    )

    def fallback() -> FinalNarrative:
        return FinalNarrative(narrative=base, provenance_notes=callouts)

    outcome = ask("finalize", FinalNarrative, data, ctx, fallback)
    text = outcome.value.narrative.strip() or base
    for line in [*callouts, *outcome.value.provenance_notes]:
        if line and line not in text:
            text = f"{text} {line}"
    return text, outcome
