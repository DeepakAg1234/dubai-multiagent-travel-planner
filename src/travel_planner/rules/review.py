"""Rule-based review. Plan issues beat budget issues."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta

from travel_planner.models import (
    BudgetReport,
    Constraints,
    Holiday,
    Itinerary,
    Place,
    Restaurant,
    ReviewReport,
    Violation,
)
from travel_planner.models.trip import RouteTarget
from travel_planner.rules.holidays import (
    CROWD_CATEGORIES,
    HERITAGE_CATEGORIES,
    effects_on,
)
from travel_planner.rules.hours import minutes_between, time_in_window, window_on
from travel_planner.rules.sequencing import active_minutes
from travel_planner.state import TripState

FUTURE_MUSEUM_ID = "place-museum-of-the-future"
PACE_LIMITS: dict[str, tuple[int, int]] = {
    "relaxed": (120, 360),
    "balanced": (180, 540),
    "packed": (240, 720),
}
MAX_LEG_MINUTES = 90
DUPLICATE_LIMIT = 1


def _day_date(constraints: Constraints, day_number: int) -> date | None:
    if constraints.start_date is None:
        return None
    return constraints.start_date + timedelta(days=day_number - 1)


def check_budget(report: BudgetReport | None, constraints: Constraints) -> list[Violation]:
    if report is None:
        return [
            Violation(
                rule="budget_compliance",
                severity="blocker",
                detail="No budget report was computed.",
                route_to="budget_adjust",
            )
        ]
    if constraints.budget_aed is None:
        return []
    if report.within_budget and report.total_aed <= constraints.budget_aed:
        return []
    return [
        Violation(
            rule="budget_compliance",
            severity="blocker",
            detail=(
                f"Plan AED {report.total_aed:g} exceeds budget AED {constraints.budget_aed:g}"
                if report.total_aed > constraints.budget_aed
                else f"Budget AED {constraints.budget_aed:g} is below the minimum viable trip."
            ),
            route_to="budget_adjust",
        )
    ]


def check_day_length(itinerary: Itinerary, constraints: Constraints) -> list[Violation]:
    low, high = PACE_LIMITS[constraints.pace]
    violations: list[Violation] = []
    for day in itinerary.days:
        minutes = active_minutes(day)
        if minutes > high:
            violations.append(
                Violation(
                    rule="day_length",
                    severity="blocker",
                    detail=(
                        f"Day {day.day} is {minutes} active minutes; "
                        f"{constraints.pace} pace caps at {high}."
                    ),
                    route_to="orchestrator_revise",
                )
            )
        elif minutes < low and any(slot.kind == "activity" for slot in day.slots):
            violations.append(
                Violation(
                    rule="day_length",
                    severity="warning",
                    detail=(
                        f"Day {day.day} is light ({minutes} active minutes) "
                        f"for a {constraints.pace} pace."
                    ),
                    route_to="orchestrator_revise",
                )
            )
    return violations


def check_travel(itinerary: Itinerary) -> list[Violation]:
    violations: list[Violation] = []
    for day in itinerary.days:
        for leg in day.legs:
            if leg.minutes > MAX_LEG_MINUTES:
                violations.append(
                    Violation(
                        rule="travel_feasibility",
                        severity="blocker",
                        detail=(
                            f"Day {day.day} leg {leg.from_id} → {leg.to_id} "
                            f"is {leg.minutes} minutes."
                        ),
                        route_to="orchestrator_revise",
                    )
                )
        transfers = [slot for slot in day.slots if slot.kind == "transfer"]
        for slot in transfers:
            span = minutes_between(slot.start, slot.end)
            if span < 0:
                violations.append(
                    Violation(
                        rule="travel_feasibility",
                        severity="blocker",
                        detail=f"Day {day.day} transfer does not fit between slots.",
                        route_to="orchestrator_revise",
                    )
                )
    return violations


def check_opening_hours(
    itinerary: Itinerary,
    constraints: Constraints,
    places: Mapping[str, Place],
    restaurants: Mapping[str, Restaurant],
    holidays: list[Holiday],
) -> list[Violation]:
    violations: list[Violation] = []
    for day in itinerary.days:
        when = _day_date(constraints, day.day)
        effects = effects_on(holidays, when) if when else None
        for slot in day.slots:
            if slot.kind not in {"activity", "meal"} or not slot.place_id:
                continue
            entity: Place | Restaurant | None = places.get(slot.place_id) or restaurants.get(
                slot.place_id
            )
            if entity is None or when is None:
                continue
            if (
                effects
                and effects.heritage_may_close
                and isinstance(entity, Place)
                and entity.category in HERITAGE_CATEGORIES
            ):
                violations.append(
                    Violation(
                        rule="opening_hours",
                        severity="blocker",
                        detail=(
                            f"{entity.name} is a heritage venue on Eid first day "
                            f"({when.isoformat()}) and should not be scheduled."
                        ),
                        route_to="orchestrator_revise",
                    )
                )
                continue
            if slot.kind == "meal" and effects and effects.drop_lunch:
                note = (slot.notes or "").lower()
                if "lunch" in note:
                    violations.append(
                        Violation(
                            rule="opening_hours",
                            severity="blocker",
                            detail=f"Lunch is scheduled on a drop_lunch day ({when.isoformat()}).",
                            route_to="orchestrator_revise",
                        )
                    )
            window = window_on(entity.opening_hours, when)
            if window and not (
                time_in_window(slot.start, window) and time_in_window(slot.end, window)
            ):
                violations.append(
                    Violation(
                        rule="opening_hours",
                        severity="blocker",
                        detail=f"{entity.name} on day {day.day} is outside opening hours.",
                        route_to="orchestrator_revise",
                    )
                )
    return violations


def check_operational_status(itinerary: Itinerary, places: Mapping[str, Place]) -> list[Violation]:
    violations: list[Violation] = []
    for day in itinerary.days:
        for slot in day.slots:
            if not slot.place_id:
                continue
            if slot.place_id == FUTURE_MUSEUM_ID:
                violations.append(
                    Violation(
                        rule="operational_status",
                        severity="blocker",
                        detail="Museum of the Future is reopening and cannot be booked.",
                        route_to="orchestrator_revise",
                    )
                )
                continue
            place = places.get(slot.place_id)
            if place is None:
                continue
            if place.operational_status in {"closed", "reopening"}:
                violations.append(
                    Violation(
                        rule="operational_status",
                        severity="blocker",
                        detail=(
                            f"{place.name} is {place.operational_status} "
                            "and must leave the draft."
                        ),
                        route_to="orchestrator_revise",
                    )
                )
    return violations


def check_duplicates(itinerary: Itinerary) -> list[Violation]:
    seen: dict[str, int] = {}
    violations: list[Violation] = []
    for day in itinerary.days:
        for slot in day.slots:
            if slot.kind != "activity" or not slot.place_id:
                continue
            seen[slot.place_id] = seen.get(slot.place_id, 0) + 1
    for place_id, count in seen.items():
        if count > DUPLICATE_LIMIT:
            violations.append(
                Violation(
                    rule="duplicates",
                    severity="blocker",
                    detail=f"{place_id} appears {count} times.",
                    route_to="orchestrator_revise",
                )
            )
    return violations


def check_completeness(
    itinerary: Itinerary,
    constraints: Constraints,
    holidays: list[Holiday],
) -> list[Violation]:
    violations: list[Violation] = []
    if itinerary.stay is None:
        violations.append(
            Violation(
                rule="completeness",
                severity="blocker",
                detail="Itinerary has no lodging.",
                route_to="orchestrator_revise",
            )
        )
    for day in itinerary.days:
        when = _day_date(constraints, day.day)
        effects = effects_on(holidays, when) if when else None
        drop_lunch = bool(effects and effects.drop_lunch)
        kinds = {slot.kind for slot in day.slots}
        meals = [(slot.notes or "").lower() for slot in day.slots if slot.kind == "meal"]
        if "activity" not in kinds:
            violations.append(
                Violation(
                    rule="completeness",
                    severity="blocker",
                    detail=f"Day {day.day} has no activities.",
                    route_to="orchestrator_revise",
                )
            )
        if not drop_lunch and not any("lunch" in note for note in meals):
            violations.append(
                Violation(
                    rule="completeness",
                    severity="blocker",
                    detail=f"Day {day.day} is missing lunch.",
                    route_to="orchestrator_revise",
                )
            )
        if not any("dinner" in note for note in meals):
            violations.append(
                Violation(
                    rule="completeness",
                    severity="warning",
                    detail=f"Day {day.day} is missing dinner.",
                    route_to="orchestrator_revise",
                )
            )
    return violations


def check_crowds(
    itinerary: Itinerary,
    constraints: Constraints,
    places: Mapping[str, Place],
    holidays: list[Holiday],
) -> list[Violation]:
    if not constraints.avoid_crowds:
        return []
    violations: list[Violation] = []
    for day in itinerary.days:
        when = _day_date(constraints, day.day)
        effects = effects_on(holidays, when) if when else None
        for slot in day.slots:
            if slot.kind != "activity" or not slot.place_id:
                continue
            place = places.get(slot.place_id)
            if place is None:
                continue
            holiday_crowd = bool(
                effects and effects.high_crowd and place.category in CROWD_CATEGORIES
            )
            if place.crowd_level == "high" or holiday_crowd:
                violations.append(
                    Violation(
                        rule="crowds",
                        severity="blocker",
                        detail=f"{place.name} is high-crowd on day {day.day}.",
                        route_to="orchestrator_revise",
                    )
                )
    return violations


def check_provenance(report: BudgetReport | None) -> list[Violation]:
    if report is None:
        return []
    violations: list[Violation] = []
    for line in report.lines:
        if not line.provenance or not line.source:
            violations.append(
                Violation(
                    rule="provenance",
                    severity="blocker",
                    detail=f"Cost line '{line.item}' is missing provenance.",
                    route_to="orchestrator_revise",
                )
            )
    return violations


def check_interest_coverage(
    itinerary: Itinerary,
    constraints: Constraints,
    places: Mapping[str, Place],
) -> list[Violation]:
    if not constraints.interests:
        return []
    tags: set[str] = set()
    categories: set[str] = set()
    has_meal = False
    for day in itinerary.days:
        for slot in day.slots:
            if slot.kind == "meal":
                has_meal = True
            if slot.kind != "activity" or not slot.place_id:
                continue
            place = places.get(slot.place_id)
            if place is None:
                continue
            tags.update(tag.lower() for tag in place.tags)
            categories.add(place.category.lower())
    missing: list[str] = []
    for interest in constraints.interests:
        key = interest.lower()
        if key in {"food", "dining", "restaurants"}:
            if not has_meal:
                missing.append(interest)
            continue
        if key in tags or key in categories:
            continue
        if key.rstrip("s") in tags or key.rstrip("s") in categories:
            continue
        if key in {"beaches", "beach"} and ("beach" in tags or "beach" in categories):
            continue
        missing.append(interest)
    if not missing:
        return []
    return [
        Violation(
            rule="interest_coverage",
            severity="warning",
            detail=f"Interests not covered: {', '.join(missing)}.",
            route_to="orchestrator_revise",
        )
    ]


def preferred_route(report: ReviewReport) -> RouteTarget:
    if report.passed:
        return "none"
    blockers = [row for row in report.violations if row.severity == "blocker"]
    if any(row.route_to == "orchestrator_revise" for row in blockers):
        return "orchestrator_revise"
    if any(row.route_to == "budget_adjust" for row in blockers):
        return "budget_adjust"
    return "none"


def run_rules(
    state: TripState | Mapping[str, object],
    *,
    places: Mapping[str, Place] | None = None,
    restaurants: Mapping[str, Restaurant] | None = None,
    holidays: list[Holiday] | None = None,
) -> ReviewReport:
    constraints = state.get("constraints")  # type: ignore[union-attr]
    itinerary = state.get("draft_itinerary")  # type: ignore[union-attr]
    budget = state.get("budget_report")  # type: ignore[union-attr]
    candidates = state.get("candidates")  # type: ignore[union-attr]
    places = dict(places or {})
    restaurants = dict(restaurants or {})
    holidays = list(holidays or [])
    if candidates is not None:
        for place in getattr(candidates, "places", []):
            places.setdefault(place.id, place)
        for row in getattr(candidates, "restaurants", []):
            restaurants.setdefault(row.id, row)

    violations: list[Violation] = []
    if constraints is None:
        violations.append(
            Violation(
                rule="completeness",
                severity="blocker",
                detail="Missing constraints.",
                route_to="orchestrator_revise",
            )
        )
        return _report(violations)
    if itinerary is None:
        violations.append(
            Violation(
                rule="completeness",
                severity="blocker",
                detail="Missing draft itinerary.",
                route_to="orchestrator_revise",
            )
        )
        return _report(violations)

    violations.extend(check_operational_status(itinerary, places))
    violations.extend(check_opening_hours(itinerary, constraints, places, restaurants, holidays))
    violations.extend(check_duplicates(itinerary))
    violations.extend(check_completeness(itinerary, constraints, holidays))
    violations.extend(check_day_length(itinerary, constraints))
    violations.extend(check_travel(itinerary))
    violations.extend(check_crowds(itinerary, constraints, places, holidays))
    violations.extend(check_interest_coverage(itinerary, constraints, places))
    violations.extend(check_provenance(budget if isinstance(budget, BudgetReport) else None))
    violations.extend(
        check_budget(budget if isinstance(budget, BudgetReport) else None, constraints)
    )

    return _report(violations)


def _report(violations: list[Violation]) -> ReviewReport:
    blockers = [row for row in violations if row.severity == "blocker"]
    report = ReviewReport(
        passed=not blockers,
        violations=violations,
        scores={
            "blockers": float(len(blockers)),
            "warnings": float(sum(1 for row in violations if row.severity == "warning")),
        },
    )
    report.scores["route"] = {
        "none": 0.0,
        "budget_adjust": 1.0,
        "orchestrator_revise": 2.0,
    }[preferred_route(report)]
    return report
