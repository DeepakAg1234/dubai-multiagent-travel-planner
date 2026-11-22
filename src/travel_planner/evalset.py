"""Offline evaluation cases and scores for the locked catalog.

Thresholds match the Phase 7 exit check: every cost line has provenance,
budget is inside the cap or explicitly flagged, no closed place is scheduled,
and no activity is duplicated. Holiday and schedule scores use the same rules
as review.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, time, timedelta

from travel_planner.config import Settings
from travel_planner.models import (
    BudgetReport,
    Constraints,
    Holiday,
    Itinerary,
    Place,
    ReviewReport,
)
from travel_planner.rules.holidays import (
    CROWD_CATEGORIES,
    HERITAGE_CATEGORIES,
    effects_on,
)
from travel_planner.rules.hours import overlaps
from travel_planner.rules.review import check_interest_coverage

HEAT_START = time(12, 0)
HEAT_END = time(16, 0)
SCHEDULE_RULES = frozenset({"travel_feasibility", "opening_hours", "day_length"})
FUTURE_MUSEUM = "place-museum-of-the-future"


@dataclass(frozen=True)
class EvalCase:
    id: str
    request: str
    expect_flagged_budget: bool = False


EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        "example",
        "4 days in Dubai, culture, food, and beaches, AED 5000, "
        "affordable hotel, avoid crowds, start:2026-11-18",
    ),
    EvalCase(
        "one-day",
        "1 day in Dubai, culture, AED 3000, affordable hotel, start:2026-11-18",
    ),
    EvalCase(
        "seven-day",
        "7 days in Dubai, culture, food, AED 12000, affordable hotel, start:2026-11-18",
    ),
    EvalCase(
        "mid-tier",
        "2 days in Dubai, landmark, mid hotel, AED 8000, start:2026-04-10",
    ),
    EvalCase(
        "family",
        "3 days in Dubai, family, AED 8000, affordable hotel, start:2026-11-18",
    ),
    EvalCase(
        "ramadan",
        "2 days in Dubai, culture, AED 5000, affordable hotel, start:2026-02-18",
    ),
    EvalCase(
        "eid-first-day",
        "1 day in Dubai, culture, AED 5000, affordable hotel, start:2026-03-19",
    ),
    EvalCase(
        "national-day",
        "2 days in Dubai, culture, AED 5000, affordable hotel, avoid crowds, start:2026-12-02",
    ),
    EvalCase(
        "july",
        "2 days in Dubai, beaches, AED 5000, affordable hotel, start:2026-07-06",
    ),
    EvalCase(
        "business-bay",
        "2 days in Business Bay, culture, AED 5000, affordable hotel, start:2026-11-18",
    ),
)


@dataclass
class CaseScore:
    id: str
    request: str
    budget_compliant: bool = False
    budget_flagged: bool = False
    schedule_feasible: bool = False
    interest_coverage: float = 0.0
    duplicate_rate: float = 1.0
    closed_place_rate: float = 1.0
    holiday_adherence: bool = False
    provenance_complete: bool = False
    passed: bool = False
    total_aed: float | None = None
    revision_count: int = 0
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def offline_settings() -> Settings:
    """Stubs and curated data only, even when the shell has provider keys."""

    return Settings(
        llm_provider="ollama",
        ollama_api_key="",
        groq_api_key="",
        anthropic_api_key="",
        gemini_api_key="",
        llm_api_key="",
        ors_api_key="",
        use_live_apis=False,
        cache_store_url="",
        checkpoint_store_url="",
    )


def score_run(
    case: EvalCase,
    values: dict[str, object],
    places: dict[str, Place],
    holidays: list[Holiday],
) -> CaseScore:
    score = CaseScore(id=case.id, request=case.request)
    constraints = values.get("constraints")
    final = values.get("final_itinerary")
    report = values.get("budget_report")
    review = values.get("review_report")
    raw_count = values.get("revision_count")
    score.revision_count = raw_count if isinstance(raw_count, int) else 0
    if not isinstance(constraints, Constraints) or not isinstance(final, Itinerary):
        score.notes.append("Run did not produce constraints and a final itinerary.")
        return score
    budget = report if isinstance(report, BudgetReport) else final.budget
    review_report = review if isinstance(review, ReviewReport) else None
    score.passed = bool(review_report.passed) if review_report is not None else False
    score.total_aed = None if budget is None else budget.total_aed
    score.budget_compliant = _budget_compliant(budget, constraints)
    score.budget_flagged = _budget_flagged(budget, final)
    score.schedule_feasible = _schedule_feasible(review_report)
    score.interest_coverage = _interest_coverage(final, constraints, places)
    score.duplicate_rate = _duplicate_rate(final)
    score.closed_place_rate = _closed_rate(final, places)
    score.holiday_adherence = _holiday_ok(final, constraints, places, holidays)
    score.provenance_complete = _provenance_ok(budget)
    if case.expect_flagged_budget and not score.budget_flagged:
        score.notes.append("Expected a flagged budget below the hotel floor.")
    return score


def threshold_failures(scores: list[CaseScore]) -> list[str]:
    """Human-readable misses against the Phase 7 exit thresholds."""

    failures: list[str] = []
    if len(scores) < 8:
        failures.append(f"Eval set has {len(scores)} cases; need 8 to 10.")
    for score in scores:
        if not (score.budget_compliant or score.budget_flagged):
            failures.append(f"{score.id}: budget is neither compliant nor flagged")
        if not score.schedule_feasible:
            failures.append(f"{score.id}: schedule is not feasible")
        if not score.holiday_adherence:
            failures.append(f"{score.id}: holiday rules were not followed")
        if score.closed_place_rate != 0:
            failures.append(f"{score.id}: closed-place rate {score.closed_place_rate}")
        if score.duplicate_rate != 0:
            failures.append(f"{score.id}: duplicate rate {score.duplicate_rate}")
        if not score.provenance_complete:
            failures.append(f"{score.id}: a cost line is missing provenance")
    example = next((row for row in scores if row.id == "example"), None)
    if example is not None and not example.budget_compliant:
        failures.append("example: AED 5000 request is over budget")
    if not any(row.passed for row in scores):
        failures.append("No eval case passed review.")
    return failures


def _budget_compliant(report: BudgetReport | None, constraints: Constraints) -> bool:
    if report is None or constraints.budget_aed is None:
        return False
    return bool(report.within_budget and report.total_aed <= constraints.budget_aed)


def _budget_flagged(report: BudgetReport | None, itinerary: Itinerary) -> bool:
    texts = list(itinerary.warnings)
    if report is not None:
        texts.extend(item.description for item in report.alternatives)
    blob = " ".join(texts).lower()
    return "hotel floor" in blob or "below the minimum" in blob


def _schedule_feasible(report: ReviewReport | None) -> bool:
    if report is None:
        return False
    return not any(
        row.severity == "blocker" and row.rule in SCHEDULE_RULES for row in report.violations
    )


def _interest_coverage(
    itinerary: Itinerary,
    constraints: Constraints,
    places: dict[str, Place],
) -> float:
    interests = [item for item in constraints.interests if item.strip()]
    if not interests:
        return 1.0
    missing = check_interest_coverage(itinerary, constraints, places)
    if not missing:
        return 1.0
    detail = missing[0].detail
    named = [
        part.strip() for part in detail.split(":", 1)[-1].strip(" .").split(",") if part.strip()
    ]
    covered = max(0, len(interests) - len(named))
    return round(covered / len(interests), 2)


def _activity_ids(itinerary: Itinerary) -> list[str]:
    return [
        slot.place_id
        for day in itinerary.days
        for slot in day.slots
        if slot.kind == "activity" and slot.place_id
    ]


def _duplicate_rate(itinerary: Itinerary) -> float:
    ids = _activity_ids(itinerary)
    if not ids:
        return 1.0
    extra = len(ids) - len(set(ids))
    return round(extra / len(ids), 4)


def _closed_rate(itinerary: Itinerary, places: dict[str, Place]) -> float:
    ids = _activity_ids(itinerary)
    if not ids:
        return 1.0
    closed = 0
    for place_id in ids:
        if place_id == FUTURE_MUSEUM:
            closed += 1
            continue
        place = places.get(place_id)
        if place is not None and place.operational_status in {"closed", "reopening"}:
            closed += 1
    return round(closed / len(ids), 4)


def _holiday_ok(
    itinerary: Itinerary,
    constraints: Constraints,
    places: dict[str, Place],
    holidays: list[Holiday],
) -> bool:
    if constraints.start_date is None:
        return True
    for day in itinerary.days:
        when = constraints.start_date + timedelta(days=day.day - 1)
        effects = effects_on(holidays, when)
        if effects is None:
            continue
        for slot in day.slots:
            if slot.kind == "meal" and effects.drop_lunch and "lunch" in (slot.notes or "").lower():
                return False
            if slot.kind != "activity" or not slot.place_id:
                continue
            place = places.get(slot.place_id)
            if place is None:
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


def _provenance_ok(report: BudgetReport | None) -> bool:
    if report is None or not report.lines:
        return False
    return all(line.provenance and line.source for line in report.lines)


def outdoor_in_heat(itinerary: Itinerary, places: dict[str, Place]) -> bool:
    """True when an outdoor activity overlaps 12:00–16:00."""

    for day in itinerary.days:
        for slot in day.slots:
            if slot.kind != "activity" or not slot.place_id:
                continue
            place = places.get(slot.place_id)
            if place is None or place.indoor:
                continue
            if overlaps(slot.start, slot.end, HEAT_START, HEAT_END):
                return True
    return False


def day_on(constraints: Constraints, day_number: int) -> date | None:
    if constraints.start_date is None:
        return None
    return constraints.start_date + timedelta(days=day_number - 1)
