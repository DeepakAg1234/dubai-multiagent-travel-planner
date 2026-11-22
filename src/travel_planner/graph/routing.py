"""Conditional edges. Routing is plain Python so the loops stay testable."""

from travel_planner.state import TripState


def route_after_parse(state: TripState) -> str:
    if state.get("constraints") is None:
        return "ask_user"
    return "orchestrator_plan"


def route_after_review(state: TripState, *, max_revisions: int = 3) -> str:
    """Plan blockers beat budget blockers. The cap finalizes with warnings."""

    report = state.get("review_report")
    if report is None or report.passed:
        return "finalize"
    if int(state.get("revision_count") or 0) >= max_revisions:
        return "finalize"
    blockers = [row for row in report.violations if row.severity == "blocker"]
    if any(row.route_to == "orchestrator_revise" for row in blockers):
        return "orchestrator_revise"
    return "budget_adjust"


def bind_review_route(max_revisions: int):
    def _route(state: TripState) -> str:
        return route_after_review(state, max_revisions=max_revisions)

    return _route
