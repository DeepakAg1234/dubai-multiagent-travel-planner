"""Graph paths on the curated SQLite catalog. Agents are stubs."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from travel_planner.evalset import offline_settings
from travel_planner.graph.routing import route_after_parse, route_after_review
from travel_planner.models import ReviewReport, Violation
from travel_planner.service import PlannerService

ROOT = Path(__file__).resolve().parents[1]
PASS_REQUEST = (
    "4 days in Dubai, culture, food, and beaches, AED 5000, "
    "affordable hotel, start:2026-11-18"
)
FUTURE_MUSEUM = "place-museum-of-the-future"


@pytest.fixture(scope="module")
def service() -> PlannerService:
    return PlannerService(offline_settings())


def test_routing_helpers():
    assert route_after_parse({"constraints": None}) == "ask_user"  # type: ignore[arg-type]
    assert route_after_parse({"constraints": object()}) == "orchestrator_plan"  # type: ignore[arg-type]
    passed = ReviewReport(passed=True, violations=[])
    assert route_after_review({"review_report": passed, "revision_count": 0}) == "finalize"  # type: ignore[arg-type]
    over = ReviewReport(
        passed=False,
        violations=[
            Violation(
                rule="budget_compliance",
                severity="blocker",
                detail="over",
                route_to="budget_adjust",
            )
        ],
    )
    assert route_after_review({"review_report": over, "revision_count": 0}) == "budget_adjust"  # type: ignore[arg-type]
    closed = ReviewReport(
        passed=False,
        violations=[
            Violation(
                rule="operational_status",
                severity="blocker",
                detail="closed",
                route_to="orchestrator_revise",
            ),
            Violation(
                rule="budget_compliance",
                severity="blocker",
                detail="over",
                route_to="budget_adjust",
            ),
        ],
    )
    assert (
        route_after_review({"review_report": closed, "revision_count": 1}) == "orchestrator_revise"
    )  # type: ignore[arg-type]
    assert route_after_review({"review_report": over, "revision_count": 3}) == "finalize"  # type: ignore[arg-type]


def test_mermaid_topology(service: PlannerService):
    diagram = service.mermaid()
    for name in (
        "parse_request",
        "ask_user",
        "orchestrator_plan",
        "destination_research",
        "logistics_prelim",
        "logistics_sequence",
        "budget",
        "budget_adjust",
        "review",
        "orchestrator_revise",
        "finalize",
    ):
        assert name in diagram
    assert "destination_research" in diagram and "logistics_prelim" in diagram
    assert "logistics_sequence" in diagram


def test_pass_on_first_review(service: PlannerService):
    events = _run(service, PASS_REQUEST, "pass")
    values = service.values("pass")
    assert values["revision_count"] == 0
    assert values["review_report"].passed  # type: ignore[union-attr]
    assert values["final_itinerary"] is not None
    assert "budget_adjust" not in {event.node for event in events}
    assert "orchestrator_revise" not in {event.node for event in events}
    _assert_event_order(events)
    _assert_parallel_before_sequence(events)
    assert values["candidates"].places  # type: ignore[union-attr]
    assert values["stay_options"]
    assert values["transport_options"]


def test_budget_revise_then_pass(service: PlannerService):
    events = _run(service, "force:budget", "budget")
    values = service.values("budget")
    nodes = [event.node for event in events]
    assert "budget_adjust" in nodes
    assert "orchestrator_revise" not in nodes
    assert values["revision_count"] >= 1
    assert values["review_report"].passed  # type: ignore[union-attr]
    assert values["budget_report"].within_budget  # type: ignore[union-attr]
    assert values["final_itinerary"] is not None
    _assert_revision_between(events, "budget_adjust")


def test_plan_revise_then_pass(service: PlannerService):
    events = _run(service, "force:museum", "museum")
    values = service.values("museum")
    assert "orchestrator_revise" in {event.node for event in events}
    assert FUTURE_MUSEUM in values["excluded_ids"]
    assert values["review_report"].passed  # type: ignore[union-attr]
    final = values["final_itinerary"]
    scheduled = [
        slot.place_id
        for day in final.days  # type: ignore[union-attr]
        for slot in day.slots
    ]
    assert FUTURE_MUSEUM not in scheduled
    _assert_revision_between(events, "orchestrator_revise")


def test_max_revisions_finalize_with_warnings(service: PlannerService):
    events = _run(service, "force:exhausted", "floor")
    values = service.values("floor")
    assert values["revision_count"] == 3
    assert values["review_report"].passed is False  # type: ignore[union-attr]
    final = values["final_itinerary"]
    assert final is not None
    assert final.warnings  # type: ignore[union-attr]
    adjust_starts = [
        event
        for event in events
        if event.node == "budget_adjust" and event.phase == "start"
    ]
    assert len(adjust_starts) == 3
    assert events[-1].node == "finalize"
    assert events[-1].phase == "end"


def test_interrupt_and_resume(service: PlannerService):
    paused = _run(service, "clarify", "ask")
    assert service.interrupts("ask")
    assert service.values("ask").get("final_itinerary") is None
    assert any(event.node == "ask_user" and event.phase == "start" for event in paused)
    resumed = _run(
        service,
        "",
        "ask",
        resume="4 days, culture and beaches, AED 5000, start:2026-11-18",
    )
    values = service.values("ask")
    assert values["final_itinerary"] is not None
    assert values["review_report"].passed  # type: ignore[union-attr]
    assert any(event.node == "finalize" for event in resumed)


def test_parallel_nodes_keep_distinct_keys(service: PlannerService):
    _run(service, PASS_REQUEST, "parallel")
    values = service.values("parallel")
    place_ids = {place.id for place in values["candidates"].places}  # type: ignore[union-attr]
    stay_ids = {stay.id for stay in values["stay_options"]}  # type: ignore[union-attr]
    assert place_ids
    assert stay_ids
    assert place_ids.isdisjoint(stay_ids)


def test_plan_endpoint_streams_events():
    sys.path.insert(0, str(ROOT / "services" / "planner-api"))
    from api import main as api_main
    from fastapi.testclient import TestClient

    api_main._service = PlannerService(offline_settings())
    try:
        with TestClient(api_main.app) as client:
            health = client.get("/health")
            assert health.status_code == 200
            with client.stream(
                "POST",
                "/plan",
                json={"request": "2 days culture beaches AED 5000 start:2026-11-18"},
            ) as response:
                assert response.status_code == 200
                body = "".join(response.iter_text())
    finally:
        api_main._service = None
    assert '"node":"parse_request"' in body or '"node": "parse_request"' in body
    assert "event: done" in body


def _run(
    service: PlannerService,
    request: str,
    thread_id: str,
    *,
    resume: object | None = None,
) -> list:
    return list(service.run(request, thread_id=thread_id, resume=resume))


def _assert_event_order(events) -> None:
    sequence = [
        "parse_request",
        "orchestrator_plan",
        "logistics_sequence",
        "budget",
        "review",
        "finalize",
    ]
    cursor = -1
    for name in sequence:
        start = _index(events, name, "start", cursor + 1)
        end = _index(events, name, "end", start + 1)
        assert start < end
        cursor = end


def _assert_parallel_before_sequence(events) -> None:
    sequence_start = _index(events, "logistics_sequence", "start")
    for name in ("destination_research", "logistics_prelim"):
        assert _index(events, name, "start") < _index(events, name, "end") < sequence_start


def _assert_revision_between(events, node: str) -> None:
    start = _index(events, node, "start")
    end = _index(events, node, "end", start + 1)
    revisions = [
        event
        for event in events[start + 1 : end]
        if event.node == node and event.phase == "revision"
    ]
    assert revisions


def _index(events, node: str, phase: str, start: int = 0) -> int:
    for index, event in enumerate(events):
        if index >= start and event.node == node and event.phase == phase:
            return index
    raise AssertionError(f"missing {node} {phase}")
