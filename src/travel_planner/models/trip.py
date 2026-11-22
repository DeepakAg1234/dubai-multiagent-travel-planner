"""Request, plan, itinerary, budget, and review models."""

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field

from travel_planner.models.catalog import (
    Place,
    Restaurant,
    StayOption,
    TransportMode,
)
from travel_planner.models.common import Sourced

BudgetCategory = Literal["accommodation", "food", "transport", "activities", "buffer"]
SlotKind = Literal["activity", "meal", "transfer", "rest", "checkin", "checkout"]
RouteTarget = Literal["budget_adjust", "orchestrator_revise", "none"]
AlternativeKind = Literal[
    "cheaper_hotel",
    "paid_to_free",
    "taxi_to_metro",
    "cheaper_dinner",
    "other",
]
ExcludedCost = Literal["flights"]


def _default_excludes() -> list[ExcludedCost]:
    return ["flights"]


class Constraints(BaseModel):
    days: int = Field(ge=1, le=7)
    budget_aed: float | None = None
    budget_scope: Literal["total", "per_person"] = "total"
    travelers: int = Field(default=1, ge=1)
    excludes: list[ExcludedCost] = Field(default_factory=_default_excludes)
    interests: list[str] = Field(default_factory=list)
    hotel_tier: Literal["budget", "mid", "luxury"] | None = None
    avoid_crowds: bool = False
    pace: Literal["relaxed", "balanced", "packed"] = "balanced"
    start_date: date | None = None
    dietary: list[str] = Field(default_factory=list)
    mobility: str | None = None


class Leg(Sourced):
    from_id: str
    to_id: str
    mode: TransportMode
    minutes: int = Field(ge=0)
    distance_km: float = Field(ge=0)
    cost_aed: float | None = Field(default=None, ge=0)


class Slot(BaseModel):
    start: time
    end: time
    place_id: str | None = None
    kind: SlotKind
    notes: str | None = None


class DayPlan(BaseModel):
    day: int = Field(ge=1)
    theme: str
    slots: list[Slot] = Field(default_factory=list)
    legs: list[Leg] = Field(default_factory=list)
    holiday_note: str | None = None


class Alternative(BaseModel):
    kind: AlternativeKind
    description: str
    savings_aed: float
    new_total_aed: float = Field(ge=0)
    replaces_id: str | None = None
    with_id: str | None = None


class BudgetLine(Sourced):
    category: BudgetCategory
    item: str
    unit_aed: float = Field(ge=0)
    quantity: float = Field(ge=0)
    total_aed: float = Field(ge=0)


class BudgetReport(BaseModel):
    lines: list[BudgetLine]
    by_category: dict[str, float]
    total_aed: float = Field(ge=0)
    budget_aed: float | None = None
    variance_aed: float | None = None
    within_budget: bool
    alternatives: list[Alternative] = Field(default_factory=list)


class Violation(BaseModel):
    rule: str
    severity: Literal["blocker", "warning"]
    detail: str
    route_to: RouteTarget


class ReviewReport(BaseModel):
    passed: bool
    violations: list[Violation] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)


class Itinerary(BaseModel):
    days: list[DayPlan]
    stay: StayOption | None = None
    budget: BudgetReport | None = None
    provenance_summary: dict[str, float] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    revision_history: list[str] = Field(default_factory=list)
    narrative: str = ""


class DayBrief(BaseModel):
    day: int = Field(ge=1)
    theme: str
    areas: list[str] = Field(default_factory=list)
    crowd_hints: list[str] = Field(default_factory=list)


class PlanBrief(BaseModel):
    days: list[DayBrief]
    cuisine_focus: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Candidates(BaseModel):
    places: list[Place] = Field(default_factory=list)
    restaurants: list[Restaurant] = Field(default_factory=list)
    areas: list[str] = Field(default_factory=list)


class AgentEvent(BaseModel):
    ts: datetime
    node: str
    phase: Literal["start", "end", "error", "revision"]
    summary: str
    state_delta: dict[str, object] = Field(default_factory=dict)
    duration_ms: int | None = Field(default=None, ge=0)
    tokens: dict[str, int] | None = None
