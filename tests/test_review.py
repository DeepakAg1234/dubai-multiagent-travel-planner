"""Rule checks against the real seed plus small draft fixtures."""

from datetime import date, time

from travel_planner.models import (
    BudgetLine,
    BudgetReport,
    Candidates,
    Constraints,
    DayPlan,
    Itinerary,
    Leg,
    Slot,
)
from travel_planner.rules.budget import compute_budget
from travel_planner.rules.review import (
    FUTURE_MUSEUM_ID,
    preferred_route,
    run_rules,
)


def _slot(place_id: str, kind: str = "activity", notes: str | None = None) -> Slot:
    return Slot(start=time(10, 0), end=time(11, 0), place_id=place_id, kind=kind, notes=notes)


def test_museum_of_the_future_is_a_plan_blocker(seed) -> None:
    future = next(row for row in seed.places if row.id == FUTURE_MUSEUM_ID)
    stay = next(row for row in seed.hotels if row.tier == "budget").stay_option("peak")
    itinerary = Itinerary(
        stay=stay,
        days=[
            DayPlan(
                day=1,
                theme="Downtown",
                slots=[
                    _slot(future.id),
                    Slot(
                        start=time(12, 30),
                        end=time(13, 30),
                        place_id=seed.restaurants[0].id,
                        kind="meal",
                        notes="lunch",
                    ),
                    Slot(
                        start=time(19, 0),
                        end=time(20, 0),
                        place_id=seed.restaurants[1].id,
                        kind="meal",
                        notes="dinner",
                    ),
                ],
            )
        ],
    )
    state = {
        "constraints": Constraints(days=1, budget_aed=5000, start_date=date(2026, 11, 18)),
        "draft_itinerary": itinerary,
        "budget_report": BudgetReport(
            lines=[
                BudgetLine(
                    category="buffer",
                    item="ok",
                    unit_aed=1,
                    quantity=1,
                    total_aed=1,
                    provenance="estimated",
                    source="test",
                )
            ],
            by_category={"buffer": 1},
            total_aed=1,
            budget_aed=5000,
            variance_aed=4999,
            within_budget=True,
        ),
        "candidates": Candidates(places=[future], restaurants=list(seed.restaurants[:2])),
    }
    report = run_rules(state, places={future.id: future}, holidays=seed.holidays)
    assert report.passed is False
    assert any(row.rule == "operational_status" for row in report.violations)
    assert preferred_route(report) == "orchestrator_revise"


def test_plan_issues_beat_budget_issues(seed) -> None:
    future = next(row for row in seed.places if row.id == FUTURE_MUSEUM_ID)
    stay = seed.hotels[0].stay_option("peak")
    itinerary = Itinerary(
        stay=stay,
        days=[DayPlan(day=1, theme="x", slots=[_slot(future.id)])],
    )
    state = {
        "constraints": Constraints(days=1, budget_aed=10, start_date=date(2026, 11, 18)),
        "draft_itinerary": itinerary,
        "budget_report": BudgetReport(
            lines=[],
            by_category={},
            total_aed=999,
            budget_aed=10,
            variance_aed=-989,
            within_budget=False,
        ),
        "candidates": Candidates(places=[future]),
    }
    report = run_rules(state, places={future.id: future})
    assert preferred_route(report) == "orchestrator_revise"


def test_budget_only_routes_to_budget_adjust(seed) -> None:
    place = next(row for row in seed.places if row.operational_status == "open")
    stay = next(row for row in seed.hotels if row.tier == "budget").stay_option("peak")
    restaurant = seed.restaurants[0]
    itinerary = Itinerary(
        stay=stay,
        days=[
            DayPlan(
                day=1,
                theme="Old Dubai",
                slots=[
                    Slot(start=time(10, 0), end=time(12, 0), place_id=place.id, kind="activity"),
                    Slot(
                        start=time(12, 30),
                        end=time(13, 30),
                        place_id=restaurant.id,
                        kind="meal",
                        notes="lunch",
                    ),
                    Slot(
                        start=time(19, 0),
                        end=time(20, 0),
                        place_id=restaurant.id,
                        kind="meal",
                        notes="dinner",
                    ),
                ],
            )
        ],
    )
    budget = compute_budget(
        itinerary,
        Constraints(days=1, budget_aed=50, start_date=date(2026, 11, 18)),
        places={place.id: place},
        restaurants={restaurant.id: restaurant},
        hotels=seed.hotels,
        bands=seed.price_bands,
        fares=seed.fares,
    )
    state = {
        "constraints": Constraints(
            days=1,
            budget_aed=50,
            start_date=date(2026, 11, 18),
            interests=[],
        ),
        "draft_itinerary": itinerary,
        "budget_report": budget,
        "candidates": Candidates(places=[place], restaurants=[restaurant]),
    }
    report = run_rules(
        state,
        places={place.id: place},
        restaurants={restaurant.id: restaurant},
        holidays=seed.holidays,
    )
    assert report.passed is False
    assert preferred_route(report) == "budget_adjust"


def test_national_day_crowd_rule(seed) -> None:
    mall = next(row for row in seed.places if row.id == "place-the-dubai-mall")
    stay = seed.hotels[0].stay_option("peak")
    itinerary = Itinerary(
        stay=stay,
        days=[
            DayPlan(
                day=1,
                theme="mall",
                slots=[
                    _slot(mall.id),
                    Slot(
                        start=time(12, 30),
                        end=time(13, 30),
                        place_id=seed.restaurants[0].id,
                        kind="meal",
                        notes="lunch",
                    ),
                    Slot(
                        start=time(19, 0),
                        end=time(20, 0),
                        place_id=seed.restaurants[0].id,
                        kind="meal",
                        notes="dinner",
                    ),
                ],
            )
        ],
    )
    report = run_rules(
        {
            "constraints": Constraints(
                days=1,
                budget_aed=5000,
                start_date=date(2026, 12, 2),
                avoid_crowds=True,
            ),
            "draft_itinerary": itinerary,
            "budget_report": BudgetReport(
                lines=[
                    BudgetLine(
                        category="buffer",
                        item="ok",
                        unit_aed=1,
                        quantity=1,
                        total_aed=1,
                        provenance="estimated",
                        source="test",
                    )
                ],
                by_category={"buffer": 1},
                total_aed=1,
                budget_aed=5000,
                variance_aed=4999,
                within_budget=True,
            ),
            "candidates": Candidates(places=[mall]),
        },
        places={mall.id: mall},
        holidays=seed.holidays,
    )
    assert any(row.rule == "crowds" for row in report.violations)


def test_duplicate_and_long_leg(seed) -> None:
    place = next(row for row in seed.places if row.operational_status == "open")
    stay = seed.hotels[0].stay_option("peak")
    itinerary = Itinerary(
        stay=stay,
        days=[
            DayPlan(
                day=1,
                theme="x",
                slots=[
                    _slot(place.id),
                    Slot(start=time(14, 0), end=time(15, 0), place_id=place.id, kind="activity"),
                ],
                legs=[
                    Leg(
                        from_id=place.id,
                        to_id=place.id,
                        mode="taxi",
                        minutes=120,
                        distance_km=40,
                        cost_aed=80,
                        provenance="estimated",
                        source="test",
                    )
                ],
            )
        ],
    )
    report = run_rules(
        {
            "constraints": Constraints(days=1, start_date=date(2026, 11, 18)),
            "draft_itinerary": itinerary,
            "budget_report": None,
        },
        places={place.id: place},
    )
    rules = {row.rule for row in report.violations}
    assert "duplicates" in rules
    assert "travel_feasibility" in rules
