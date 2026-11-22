"""Schema tests for the Phase 1 models and shared state."""

import operator
from datetime import date, datetime, time
from typing import get_type_hints

import pytest
from pydantic import ValidationError

from travel_planner.models import (
    BudgetLine,
    Constraints,
    Hotel,
    Place,
    PriceRange,
    ToolResult,
)
from travel_planner.state import TripState


def test_constraints_reject_a_trip_longer_than_a_week() -> None:
    with pytest.raises(ValidationError):
        Constraints(days=8, budget_aed=5000, interests=["culture"])


def test_price_range_keeps_the_upper_end_above_the_lower_end() -> None:
    with pytest.raises(ValidationError):
        PriceRange(min_aed=40, max_aed=10)


def test_tool_result_carries_provenance() -> None:
    result = ToolResult[int](data=3, provenance="verified", source="rta")
    assert result.data == 3
    assert result.degraded is False


def test_place_defaults_to_open() -> None:
    place = Place(
        id="place-test",
        name="Test",
        category="museum",
        area="Old Dubai",
        lat=25.2,
        lng=55.3,
        provenance="estimated",
        source="test",
        as_of=date(2026, 11, 17),
    )
    assert place.operational_status == "open"
    assert place.timed_entry is False


def test_hotel_exposes_a_seasonal_stay_option() -> None:
    hotel = Hotel(
        id="hotel-test",
        name="Test Hotel",
        area="Downtown",
        tier="mid",
        lat=25.2,
        lng=55.27,
        peak_nightly_min=400,
        peak_nightly_max=600,
        summer_nightly_min=280,
        summer_nightly_max=450,
        provenance="estimated",
        source="test",
    )
    stay = hotel.stay_option("summer")
    assert stay.season == "summer"
    assert stay.nightly_min_aed == 280


def test_budget_line_uses_the_shared_categories() -> None:
    line = BudgetLine(
        category="buffer",
        item="contingency",
        unit_aed=10,
        quantity=1,
        total_aed=10,
        provenance="estimated",
        source="rule",
    )
    assert line.category == "buffer"


def test_trip_state_accumulates_events_and_exclusions() -> None:
    hints = get_type_hints(TripState, include_extras=True)
    assert hints["events"].__metadata__[0] is operator.add
    assert hints["excluded_ids"].__metadata__[0] is operator.add
    assert hints["warnings"].__metadata__[0] is operator.add


def test_agent_event_phase_is_closed() -> None:
    from travel_planner.models import AgentEvent

    event = AgentEvent(
        ts=datetime(2026, 11, 17, 12, 0, 0),
        node="review",
        phase="revision",
        summary="tightened the budget",
        state_delta={"revision_count": 1},
    )
    assert event.duration_ms is None
    with pytest.raises(ValidationError):
        AgentEvent(
            ts=datetime(2026, 11, 17, 12, 0, 0),
            node="review",
            phase="thinking",
            summary="no",
        )


def test_slot_accepts_a_clock_time() -> None:
    from travel_planner.models import Slot

    slot = Slot(start=time(9, 0), end=time(11, 0), kind="activity", place_id="place-test")
    assert slot.kind == "activity"
