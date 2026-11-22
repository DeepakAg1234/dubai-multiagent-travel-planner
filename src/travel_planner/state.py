"""Shared LangGraph state. Parallel nodes write different keys."""

import operator
from typing import Annotated, TypedDict

from travel_planner.models import (
    AgentEvent,
    BudgetReport,
    Candidates,
    Constraints,
    Itinerary,
    PlanBrief,
    ReviewReport,
    StayOption,
    TransportOption,
)


class TripState(TypedDict):
    raw_request: str
    constraints: Constraints | None
    assumptions: list[str]

    plan_brief: PlanBrief | None
    candidates: Candidates | None
    stay_options: list[StayOption]
    transport_options: list[TransportOption]
    draft_itinerary: Itinerary | None

    budget_report: BudgetReport | None
    review_report: ReviewReport | None

    revision_count: int
    excluded_ids: Annotated[list[str], operator.add]
    events: Annotated[list[AgentEvent], operator.add]
    warnings: Annotated[list[str], operator.add]

    final_itinerary: Itinerary | None
