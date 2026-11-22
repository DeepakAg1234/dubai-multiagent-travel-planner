"""Phase 7 exit checks: eval thresholds, catalog edge cases, and hard stops."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pytest
from langgraph.errors import GraphRecursionError, NodeTimeoutError

from travel_planner.data.areas import PLANNING_AREAS
from travel_planner.evalset import (
    EVAL_CASES,
    outdoor_in_heat,
    score_run,
    threshold_failures,
)
from travel_planner.evalset import offline_settings as stub_settings
from travel_planner.graph.build import NODE_TIMEOUT_SECONDS
from travel_planner.graph.demo import named_planning_areas
from travel_planner.graph.shortlist import meals_for_places
from travel_planner.log import configure_logging, redact, trace_inputs
from travel_planner.models import Place
from travel_planner.rules.holidays import HERITAGE_CATEGORIES
from travel_planner.rules.sequencing import sequence_itinerary
from travel_planner.service import RECURSION_LIMIT, PlannerService

ROOT = Path(__file__).resolve().parents[1]
FUTURE_MUSEUM = "place-museum-of-the-future"


@pytest.fixture(scope="module")
def offline() -> PlannerService:
    return PlannerService(settings=stub_settings())


@pytest.fixture(scope="module")
def eval_scores(offline: PlannerService):
    places = {place.id: place for place in offline.tools.places}
    scores = []
    for index, case in enumerate(EVAL_CASES):
        list(offline.run(case.request, thread_id=f"eval-{case.id}", use_live_apis=False))
        scores.append(
            score_run(case, offline.values(f"eval-{case.id}"), places, offline.tools.holidays)
        )
    return scores


def test_eval_set_meets_thresholds(eval_scores) -> None:
    assert 8 <= len(eval_scores) <= 10
    assert threshold_failures(eval_scores) == []
    example = next(row for row in eval_scores if row.id == "example")
    assert example.passed
    assert example.total_aed is not None and example.total_aed <= 5000


def test_example_events_show_distinct_nodes(offline: PlannerService) -> None:
    events = list(offline.run(EVAL_CASES[0].request, thread_id="criteria", use_live_apis=False))
    nodes = {event.node for event in events if event.phase == "end"}
    assert {"parse_request", "destination_research", "budget", "review", "finalize"} <= nodes
    assert offline.values("criteria")["final_itinerary"] is not None


def test_budget_below_hotel_floor_is_flagged(offline: PlannerService) -> None:
    request = "4 days in Dubai, culture, AED 400, affordable hotel, start:2026-11-18"
    list(offline.run(request, thread_id="floor", use_live_apis=False))
    values = offline.values("floor")
    final = values["final_itinerary"]
    report = values["budget_report"]
    assert final is not None and report is not None
    assert report.within_budget is False
    assert values["revision_count"] == 3
    text = " ".join(final.warnings) + " ".join(item.description for item in report.alternatives)
    assert "hotel floor" in text.lower() or "minimum" in text.lower()
    assert any(line.provenance for line in report.lines)


def test_business_bay_merges_with_its_metro_neighbour(offline: PlannerService) -> None:
    values = offline.values("eval-business-bay")
    final = values["final_itinerary"]
    places = {place.id: place for place in offline.tools.places}
    restaurants = {row.id: row for row in offline.tools.restaurants}
    assert final is not None and final.stay is not None
    assert final.stay.area == "Business Bay"
    activity_areas = {
        places[slot.place_id].area
        for day in final.days
        for slot in day.slots
        if slot.kind == "activity" and slot.place_id in places
    }
    assert "Business Bay" in activity_areas
    assert any("Business Bay" in day.theme for day in final.days)
    meal_areas = {
        restaurants[slot.place_id].area
        for day in final.days
        for slot in day.slots
        if slot.kind == "meal" and slot.place_id in restaurants
    }
    assert meal_areas
    assert meal_areas <= set(PLANNING_AREAS)


def test_one_day_and_seven_day_compare_passes(offline: PlannerService) -> None:
    one = offline.values("eval-one-day")["budget_report"]
    week = offline.values("eval-seven-day")["budget_report"]
    assert one is not None and week is not None
    one_items = " ".join(line.item for line in one.lines if line.category == "transport")
    week_items = " ".join(line.item for line in week.lines if line.category == "transport")
    assert one_items
    assert week_items
    assert "7-day" not in one_items
    assert "7-day" in week_items or "pay-per-trip" in week_items or "metro" in week_items


def test_missing_trip_length_asks_for_clarification(offline: PlannerService) -> None:
    events = list(offline.run("a weekend in Dubai", thread_id="clarify", use_live_apis=False))
    assert offline.interrupts("clarify")
    assert any(event.node == "ask_user" for event in events)
    assert offline.values("clarify").get("final_itinerary") is None


def test_live_apis_off_still_finishes(offline: PlannerService) -> None:
    list(
        offline.run(
            "2 days in Dubai, culture, AED 5000, affordable, start:2026-11-18",
            thread_id="apis-off",
            use_live_apis=False,
        )
    )
    final = offline.values("apis-off")["final_itinerary"]
    assert final is not None
    assert all(leg.provenance != "api" for day in final.days for leg in day.legs)


def test_malformed_model_output_falls_back(offline: PlannerService) -> None:
    def chat(_messages):
        return "not json at all"

    broken = PlannerService(settings=stub_settings(), chat=chat)
    list(
        broken.run(
            "2 days in Dubai, culture, AED 5000, affordable, start:2026-11-18",
            thread_id="malformed",
            use_live_apis=False,
        )
    )
    final = broken.values("malformed")["final_itinerary"]
    assert final is not None
    assert broken.usage.snapshot()
    assert any(row["fallbacks"] > 0 for row in broken.usage.snapshot().values())


def test_museum_request_is_revised_out(offline: PlannerService) -> None:
    list(offline.run("force:museum", thread_id="museum", use_live_apis=False))
    values = offline.values("museum")
    final = values["final_itinerary"]
    scheduled = [slot.place_id for day in final.days for slot in day.slots]
    assert FUTURE_MUSEUM not in scheduled
    assert FUTURE_MUSEUM in values["excluded_ids"]
    assert values["review_report"].passed


def test_ramadan_has_no_lunch(offline: PlannerService) -> None:
    final = offline.values("eval-ramadan")["final_itinerary"]
    assert not any(slot.notes == "lunch" for day in final.days for slot in day.slots)


def test_eid_first_day_drops_heritage_and_a_later_day_keeps_it(offline: PlannerService) -> None:
    places = {place.id: place for place in offline.tools.places}
    first = offline.values("eval-eid-first-day")["final_itinerary"]
    assert _heritage(first, places) == set()
    list(
        offline.run(
            "3 days in Dubai, culture, AED 5000, affordable hotel, start:2026-03-20",
            thread_id="eid-later",
            use_live_apis=False,
        )
    )
    later = offline.values("eid-later")["final_itinerary"]
    assert _heritage(later, places)


def test_national_day_avoid_crowds(offline: PlannerService) -> None:
    from travel_planner.rules.holidays import CROWD_CATEGORIES

    places = {place.id: place for place in offline.tools.places}
    final = offline.values("eval-national-day")["final_itinerary"]
    for day in final.days:
        for slot in day.slots:
            place = places.get(slot.place_id or "")
            if place is not None and slot.kind == "activity":
                assert place.category not in CROWD_CATEGORIES


def test_july_graph_keeps_outdoor_visits_out_of_midday(offline: PlannerService) -> None:
    places = {place.id: place for place in offline.tools.places}
    final = offline.values("eval-july")["final_itinerary"]
    assert outdoor_in_heat(final, places) is False


def test_july_fixture_inserts_a_midday_rest(offline: PlannerService) -> None:
    by_id = {place.id: place for place in offline.tools.places}
    outdoor = [
        by_id["place-jbr-beach"],
        by_id["place-dubai-marina-promenade"],
        by_id["place-the-walk-at-jbr"],
    ]
    assert all(place.indoor is False for place in outdoor)
    restaurants = [row for row in offline.tools.restaurants if row.area == "Marina / JBR"][:4]
    climate = next(row for row in offline.tools.climate if row.month == 7)
    assert climate.avg_high_c >= 35
    from travel_planner.models import Constraints

    itinerary = sequence_itinerary(
        outdoor,
        restaurants,
        Constraints(
            days=1,
            budget_aed=5000,
            interests=["beaches"],
            hotel_tier="budget",
            start_date=date(2026, 7, 6),
        ),
        holidays=offline.tools.holidays,
        climate=climate,
        stations=offline.tools.stations,
        edges=offline.tools.edges,
        fares=offline.tools.fares,
    )
    assert any(slot.kind == "rest" for day in itinerary.days for slot in day.slots)
    assert outdoor_in_heat(itinerary, {place.id: place for place in outdoor}) is False


def test_recursion_limit_stops_with_an_error_event(offline: PlannerService) -> None:
    assert RECURSION_LIMIT >= 40
    events = list(
        offline.run(
            EVAL_CASES[0].request,
            thread_id="recursion",
            use_live_apis=False,
            recursion_limit=2,
        )
    )
    assert any(event.phase == "error" and "Recursion limit" in event.summary for event in events)


def test_node_timeout_is_a_hard_stop() -> None:
    assert NODE_TIMEOUT_SECONDS == 30

    def _astream(*_args, **_kwargs):
        async def _empty():
            raise NodeTimeoutError("budget", 30.1, kind="run", run_timeout=30)
            yield  # pragma: no cover

        return _empty()

    service = PlannerService(settings=stub_settings())
    service._graph.astream = _astream  # type: ignore[method-assign]
    events = list(service.run("2 days", thread_id="timeout", use_live_apis=False))
    assert any(event.phase == "error" and "timeout" in event.summary.lower() for event in events)


def test_recursion_error_type_is_the_one_the_service_catches() -> None:
    assert issubclass(GraphRecursionError, RecursionError)


def test_default_log_redacts_keys_and_omits_the_prompt(caplog: pytest.LogCaptureFixture) -> None:
    configure_logging()
    caplog.set_level(logging.INFO, logger="travel_planner")
    logger = logging.getLogger("travel_planner")
    secret = "gsk_test_key_value"
    logger.info("loaded GROQ_API_KEY=%s", secret)
    logger.info("Authorization: Bearer %s", secret)
    rendered = caplog.text
    assert secret not in rendered
    assert "[redacted]" in rendered
    assert "weekend in the marina with a private note" not in rendered
    summary = trace_inputs(
        {"raw_request": "weekend in the marina with a private note", "revision_count": 0}
    )
    assert summary["request_chars"] == len("weekend in the marina with a private note")
    assert "marina" not in str(summary)
    assert redact(f"ORS_API_KEY={secret}") == "ORS_API_KEY=[redacted]"
    assert redact(f"ANTHROPIC_API_KEY={secret}") == "ANTHROPIC_API_KEY=[redacted]"


def test_meal_pool_covers_a_thin_area_the_picker_skipped(seed) -> None:
    place = next(
        row
        for row in seed.places
        if row.area == "Al Quoz" and row.operational_status == "open"
    )
    old_dubai = [row for row in seed.restaurants if row.area == "Old Dubai"][:2]
    covered = meals_for_places([place], old_dubai, seed.restaurants, price_band="budget")
    assert any(row.area == "Al Quoz" for row in covered)


def test_named_area_detection_ignores_bare_dubai() -> None:
    assert named_planning_areas("4 days in Dubai") == []
    assert named_planning_areas("2 days in Business Bay") == ["Business Bay"]


def test_demo_presets_and_deploy_files() -> None:
    web = (ROOT / "apps" / "web" / "lib" / "compose.ts").read_text(encoding="utf-8")
    for token in ("force:budget", "force:museum", "force:national", "force:eid"):
        assert token in web
    assert "4 days" in web
    import subprocess
    import sys

    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_deploy.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _heritage(itinerary, places: dict[str, Place]) -> set[str]:
    found: set[str] = set()
    for day in itinerary.days:
        for slot in day.slots:
            place = places.get(slot.place_id or "")
            if (
                place is not None
                and slot.kind == "activity"
                and place.category in HERITAGE_CATEGORIES
            ):
                found.add(place.id)
    return found
