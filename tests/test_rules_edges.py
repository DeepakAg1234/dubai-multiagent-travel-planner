"""Branch coverage for hours, geo, fallbacks, and remaining review rules."""

from datetime import date, time

from travel_planner.models import (
    BudgetLine,
    BudgetReport,
    Constraints,
    DayPlan,
    Itinerary,
    Leg,
    Restaurant,
    ReviewReport,
    Slot,
    Violation,
)
from travel_planner.rules.budget import (
    cheapest_budget_night,
    food_lines,
    season_for,
)
from travel_planner.rules.fares import (
    TransitGraph,
    abra_fare,
    nol_zone_for_area,
    pass_1day,
    pass_7day,
    price_existing_leg,
    silver_metro_fare,
    taxi_fare_aed,
)
from travel_planner.rules.geo import minutes_at_speed, nearest, walk_minutes
from travel_planner.rules.hours import parse_window, time_in_window, weekday_key, window_on
from travel_planner.rules.review import preferred_route, run_rules
from travel_planner.rules.sequencing import group_by_day, two_opt


def test_season_and_food_fallbacks() -> None:
    assert season_for(None) == "peak"
    restaurant = Restaurant(
        id="r",
        name="x",
        cuisine="unspecified",
        area="Downtown",
        lat=25.2,
        lng=55.27,
        price_band="mid",
        meal_types=["breakfast"],
        provenance="estimated",
        source="test",
    )
    assert food_lines([restaurant], [], 1) == []
    dinner_only = restaurant.model_copy(update={"meal_types": ["dinner"]})
    lines = food_lines([dinner_only], [], 1)
    assert lines[0].unit_aed == 70
    assert cheapest_budget_night([], "peak") == 170
    assert cheapest_budget_night([], "summer") == 120


def test_hours_and_geo_helpers() -> None:
    assert weekday_key(date(2026, 11, 18)) == "wed"
    assert parse_window("24 hours")[0] == time(0, 0)
    assert parse_window("daylight")[0] == time(7, 0)
    assert parse_window("closed") is None
    assert parse_window("12:00-00:00")[1] == time(23, 59)
    assert parse_window("nope") is None
    assert parse_window("25:00-10:00") is None
    assert window_on({"daily": "09:00-17:00"}, date(2026, 1, 1))[0] == time(9, 0)
    overnight = (time(22, 0), time(2, 0))
    assert time_in_window(time(23, 0), overnight)
    assert time_in_window(time(1, 0), overnight)
    assert minutes_at_speed(1, 0) == 0
    assert walk_minutes(0) == 0
    left = type("P", (), {"lat": 25.2, "lng": 55.27})()
    assert nearest(left, []) is None
    assert nearest(left, [left]) is left
    assert nol_zone_for_area("Dubailand") == 2


def test_fare_table_fallbacks_and_priced_legs() -> None:
    silver = silver_metro_fare([], 1)
    assert silver.price_aed == 3
    assert pass_1day([]).price_aed == 20
    assert pass_7day([], 1).price_aed == 50
    assert pass_7day([], 2).price_aed == 80
    day, _ = taxi_fare_aed([], 1, time(10, 0))
    assert day == 12
    assert abra_fare([]).price_aed == 1
    walk = price_existing_leg(
        Leg(
            from_id="a",
            to_id="b",
            mode="walk",
            minutes=5,
            distance_km=0.4,
            provenance="estimated",
            source="test",
        ),
        [],
    )
    assert walk.cost_aed == 0
    bus = price_existing_leg(
        Leg(
            from_id="a",
            to_id="b",
            mode="bus",
            minutes=15,
            distance_km=3,
            provenance="estimated",
            source="test",
        ),
        [],
    )
    assert bus.mode == "metro"
    ferry = price_existing_leg(
        Leg(
            from_id="a",
            to_id="b",
            mode="ferry",
            minutes=10,
            distance_km=1,
            provenance="estimated",
            source="test",
        ),
        [],
    )
    assert ferry.cost_aed == 1
    taxi = price_existing_leg(
        Leg(
            from_id="a",
            to_id="b",
            mode="taxi",
            minutes=10,
            distance_km=0.2,
            provenance="estimated",
            source="test",
        ),
        [],
    )
    assert taxi.cost_aed == 12


def test_graph_unknown_and_same_station(seed) -> None:
    graph = TransitGraph(seed.stations, seed.edges)
    assert graph.minutes("missing", "metro-union") is None
    assert graph.minutes("metro-union", "metro-union") == (0, [])
    empty = TransitGraph([], [])
    place = seed.places[0]
    assert empty.nearest_station(place) is None


def test_review_missing_state_and_holiday_hours(seed) -> None:
    assert run_rules({"constraints": None, "draft_itinerary": None}).passed is False
    constraints = Constraints(days=1, start_date=date(2026, 11, 18))
    missing_plan = run_rules({"constraints": constraints, "draft_itinerary": None})
    assert missing_plan.violations[0].detail.startswith("Missing draft")

    museum = next(row for row in seed.places if row.id == "place-dubai-museum")
    stay = seed.hotels[0].stay_option("peak")
    eid = Itinerary(
        stay=stay,
        days=[
            DayPlan(
                day=1,
                theme="eid",
                slots=[
                    Slot(start=time(10, 0), end=time(11, 0), place_id=museum.id, kind="activity"),
                    Slot(
                        start=time(12, 30),
                        end=time(13, 30),
                        place_id=seed.restaurants[0].id,
                        kind="meal",
                        notes="lunch",
                    ),
                ],
            )
        ],
    )
    eid_report = run_rules(
        {
            "constraints": Constraints(
                days=1, start_date=date(2026, 3, 19), interests=["food", "nightlife"]
            ),
            "draft_itinerary": eid,
            "budget_report": BudgetReport(
                lines=[
                    BudgetLine.model_construct(
                        category="food",
                        item="x",
                        unit_aed=1,
                        quantity=1,
                        total_aed=1,
                        provenance="",
                        source="",
                    )
                ],
                by_category={"food": 1},
                total_aed=1,
                budget_aed=None,
                variance_aed=None,
                within_budget=True,
            ),
        },
        places={museum.id: museum},
        restaurants={seed.restaurants[0].id: seed.restaurants[0]},
        holidays=seed.holidays,
    )
    rules = {row.rule for row in eid_report.violations}
    assert "opening_hours" in rules
    ramadan = Itinerary(
        stay=stay,
        days=[
            DayPlan(
                day=1,
                theme="ramadan",
                slots=[
                    Slot(start=time(10, 0), end=time(11, 0), place_id=museum.id, kind="activity"),
                    Slot(
                        start=time(12, 30),
                        end=time(13, 30),
                        place_id=seed.restaurants[0].id,
                        kind="meal",
                        notes="lunch",
                    ),
                ],
            )
        ],
    )
    ramadan_report = run_rules(
        {
            "constraints": Constraints(days=1, start_date=date(2026, 2, 18)),
            "draft_itinerary": ramadan,
        },
        places={museum.id: museum},
        restaurants={seed.restaurants[0].id: seed.restaurants[0]},
        holidays=seed.holidays,
    )
    assert any("Lunch is scheduled" in row.detail for row in ramadan_report.violations)
    passed = ReviewReport(passed=True, violations=[])
    assert preferred_route(passed) == "none"
    warn_only = ReviewReport(
        passed=False,
        violations=[
            Violation(rule="x", severity="warning", detail="y", route_to="orchestrator_revise")
        ],
    )
    assert preferred_route(warn_only) == "none"


def test_day_length_and_two_opt_and_thin_split(seed) -> None:
    place = next(row for row in seed.places if row.operational_status == "open")
    stay = seed.hotels[0].stay_option("peak")
    packed = Itinerary(
        stay=stay,
        days=[
            DayPlan(
                day=1,
                theme="packed",
                slots=[
                    Slot(start=time(8, 0), end=time(21, 0), place_id=place.id, kind="activity"),
                    Slot(
                        start=time(12, 0),
                        end=time(13, 0),
                        place_id=seed.restaurants[0].id,
                        kind="meal",
                        notes="lunch",
                    ),
                ],
            )
        ],
    )
    report = run_rules(
        {
            "constraints": Constraints(days=1, pace="relaxed", start_date=date(2026, 11, 18)),
            "draft_itinerary": packed,
        },
        places={place.id: place},
    )
    assert any(row.rule == "day_length" for row in report.violations)
    bay = [row for row in seed.places if row.area == "Business Bay"]
    closed = next(row for row in seed.places if row.id == "place-museum-of-the-future")
    groups = group_by_day([*bay, closed], days=3, pool=seed.places)
    assert len(groups) == 3
    assert all(place.operational_status != "reopening" for group in groups for place in group)
    ordered = two_opt(bay)
    assert {row.id for row in ordered} == {row.id for row in bay}
