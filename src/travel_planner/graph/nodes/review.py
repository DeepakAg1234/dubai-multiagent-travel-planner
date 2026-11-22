"""Stage-1 rules, then an optional Groq review that cannot clear a blocker."""

from travel_planner.graph.context import NodeContext
from travel_planner.graph.schemas import Qualitative
from travel_planner.graph.turn import ask, llm_active, with_tokens
from travel_planner.models import ReviewReport, Violation
from travel_planner.rules.review import run_rules
from travel_planner.state import TripState


def review(state: TripState, ctx: NodeContext) -> dict[str, object]:
    report = run_rules(
        state,
        places={row.id: row for row in ctx.tools.places},
        restaurants={row.id: row for row in ctx.tools.restaurants},
        holidays=ctx.tools.holidays,
    )
    outcome = None
    if llm_active("review", ctx):
        outcome = _qualitative(state, report, ctx)
        report = apply_qualitative(report, outcome.value)
    blockers = [row for row in report.violations if row.severity == "blocker"]
    summary = "Review passed." if report.passed else f"{len(blockers)} blocker(s)."
    payload: dict[str, object] = {
        "review_report": report,
        "_summary": summary,
        "_delta": {
            "passed": report.passed,
            "blockers": [row.rule for row in blockers],
        },
    }
    if outcome is None:
        return payload
    return with_tokens(outcome, payload)


def apply_qualitative(report: ReviewReport, note: Qualitative) -> ReviewReport:
    """Add warnings. A rule blocker stays, with the same route."""

    violations = list(report.violations)
    for warning in note.warnings[:5]:
        text = warning.strip()
        if not text:
            continue
        violations.append(
            Violation(
                rule="qualitative",
                severity="warning",
                detail=text[:240],
                route_to="none",
            )
        )
    blockers = [row for row in report.violations if row.severity == "blocker"]
    if note.request_revision and not blockers:
        violations.append(
            Violation(
                rule="qualitative",
                severity="blocker",
                detail=(note.note or "Qualitative review requested a revision.")[:240],
                route_to="orchestrator_revise",
            )
        )
    passed = not any(row.severity == "blocker" for row in violations)
    return ReviewReport(passed=passed, violations=violations, scores=dict(report.scores))


def _qualitative(state: TripState, report: ReviewReport, ctx: NodeContext):
    constraints = state["constraints"]
    data = "\n".join(
        [
            constraints.model_dump_json() if constraints is not None else "{}",
            report.model_dump_json(),
        ]
    )

    def fallback() -> Qualitative:
        return Qualitative()

    return ask("review", Qualitative, data, ctx, fallback)
