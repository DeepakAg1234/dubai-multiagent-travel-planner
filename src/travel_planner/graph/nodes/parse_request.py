"""Parse a free-text request. A missing provider key keeps the token scan."""

from travel_planner.graph.context import NodeContext
from travel_planner.graph.demo import force_flag, parse_request_text
from travel_planner.graph.schemas import ParseDraft
from travel_planner.graph.turn import ask, llm_active, with_tokens
from travel_planner.models import Constraints
from travel_planner.state import TripState

_TIERS = {"budget": "budget", "mid": "mid", "luxury": "luxury", "affordable": "budget"}
_PACES = {"relaxed": "relaxed", "balanced": "balanced", "packed": "packed"}


def parse_request(state: TripState, ctx: NodeContext) -> dict[str, object]:
    text = state["raw_request"]
    # Demo flags stay deterministic so a live key cannot skip a forced revision.
    if force_flag(text) or not llm_active("parse_request", ctx):
        return _from_regex(text)
    return _from_model(text, ctx)


def _from_regex(text: str) -> dict[str, object]:
    parsed = parse_request_text(text)
    if parsed.constraints is None:
        return {
            "constraints": None,
            "assumptions": parsed.assumptions,
            "_summary": "Trip length is missing; asking the user.",
            "_delta": {"clarification": "days"},
        }
    constraints = parsed.constraints
    return {
        "constraints": constraints,
        "assumptions": parsed.assumptions,
        "_summary": (
            f"{constraints.days} days, AED {constraints.budget_aed:g}, "
            f"{constraints.hotel_tier} hotel, start {constraints.start_date}."
        ),
        "_delta": {
            "days": constraints.days,
            "budget_aed": constraints.budget_aed,
            "hotel_tier": constraints.hotel_tier,
            "start_date": constraints.start_date.isoformat() if constraints.start_date else None,
            "force": parsed.force,
        },
    }


def _from_model(text: str, ctx: NodeContext) -> dict[str, object]:
    def fallback() -> ParseDraft:
        parsed = parse_request_text(text)
        if parsed.constraints is None:
            return ParseDraft(assumptions=list(parsed.assumptions))
        row = parsed.constraints
        return ParseDraft(
            days=row.days,
            budget_aed=row.budget_aed,
            travelers=row.travelers,
            interests=list(row.interests),
            hotel_tier=row.hotel_tier,
            avoid_crowds=row.avoid_crowds,
            pace=row.pace,
            start_date=row.start_date.isoformat() if row.start_date else None,
            assumptions=list(parsed.assumptions),
        )

    outcome = ask(
        "parse_request",
        ParseDraft,
        text,
        ctx,
        fallback,
        check=_check_draft,
    )
    if outcome.used_fallback and outcome.value.days is None and not outcome.value.assumptions:
        return with_tokens(outcome, _from_regex(text))
    return with_tokens(outcome, _materialize(outcome.value))


def _check_draft(draft: ParseDraft) -> str | None:
    if draft.days is not None and not 1 <= draft.days <= 7:
        return "days must be an integer from 1 to 7, or null"
    if draft.hotel_tier not in {None, "", "budget", "mid", "luxury", "affordable", "upscale"}:
        return "hotel_tier must be budget, mid, luxury, or null"
    if draft.pace not in {None, "", "relaxed", "balanced", "packed"}:
        return "pace must be relaxed, balanced, or packed"
    if draft.start_date:
        from datetime import date

        try:
            date.fromisoformat(draft.start_date[:10])
        except ValueError:
            return "start_date must be YYYY-MM-DD or null"
    return None


def _materialize(draft: ParseDraft) -> dict[str, object]:
    from datetime import date

    assumptions = [note for note in draft.assumptions if note.strip()][:6]
    if draft.days is None:
        if not assumptions:
            assumptions.append("Trip length was not specified.")
        return {
            "constraints": None,
            "assumptions": assumptions,
            "_summary": "Trip length is missing; asking the user.",
            "_delta": {"clarification": "days"},
        }
    travelers = draft.travelers if draft.travelers and draft.travelers >= 1 else 1
    if draft.travelers is None:
        assumptions.append("Travelers defaulted to 1.")
    budget = draft.budget_aed
    if budget is None:
        budget = 5000.0
        assumptions.append("Budget defaulted to AED 5000 for the group, accommodation included.")
    else:
        assumptions.append("Budget is the total for the group, including accommodation.")
    start = date.fromisoformat(draft.start_date[:10]) if draft.start_date else None
    if start is None:
        start = date(2026, 11, 18)
        assumptions.append(
            f"Start date defaulted to {start.isoformat()}, off the holiday calendar."
        )
    tier = _TIERS.get((draft.hotel_tier or "").lower())
    if (draft.hotel_tier or "").lower() == "upscale":
        assumptions.append("Restaurant band upscale was not copied onto the hotel tier.")
    if tier is None:
        tier = "budget"
        assumptions.append("Hotel tier defaulted to budget (affordable).")
    pace = _PACES.get((draft.pace or "").lower(), "balanced")
    if draft.pace is None:
        assumptions.append("Pace defaulted to balanced.")
    interests = [item.strip().lower() for item in draft.interests if item.strip()][:8]
    if not interests:
        interests = ["culture", "food", "beaches"]
        assumptions.append("Interests defaulted to culture, food, and beaches.")
    assumptions.append("Flights are excluded.")
    constraints = Constraints(
        days=draft.days,
        budget_aed=budget,
        budget_scope="total",
        travelers=travelers,
        excludes=["flights"],
        interests=interests,
        hotel_tier=tier,  # type: ignore[arg-type]
        avoid_crowds=draft.avoid_crowds,
        pace=pace,  # type: ignore[arg-type]
        start_date=start,
    )
    return {
        "constraints": constraints,
        "assumptions": assumptions,
        "_summary": (
            f"{constraints.days} days, AED {constraints.budget_aed:g}, "
            f"{constraints.hotel_tier} hotel, start {constraints.start_date}."
        ),
        "_delta": {
            "days": constraints.days,
            "budget_aed": constraints.budget_aed,
            "hotel_tier": constraints.hotel_tier,
            "start_date": constraints.start_date.isoformat() if constraints.start_date else None,
        },
    }
