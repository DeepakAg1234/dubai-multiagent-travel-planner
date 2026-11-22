"""Demo flags and the stub request parser.

The flags use catalog facts: a luxury stay against a mid-tier budget, the
reopening Museum of the Future, Eid al-Fitr 2026-03-19, National Day
2026-12-02 with crowd avoidance, or a budget under the hotel floor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from travel_planner.data.areas import PLANNING_AREAS
from travel_planner.models import Constraints

_FORCE = re.compile(
    r"force(?:_revision)?\s*[:=]\s*(budget|museum|eid|national(?:_day)?|exhausted)",
    re.IGNORECASE,
)
_DAYS = re.compile(r"\b([1-7])\s*-?\s*days?\b", re.IGNORECASE)
_DAYS_LABEL = re.compile(r"\bdays?\s*[:=]\s*([1-7])\b", re.IGNORECASE)
_BARE_DAY = re.compile(r"^\s*([1-7])\s*$")
_BUDGET = re.compile(
    r"\b(?:aed|budget)\s*[:=]?\s*(\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)
_START = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_INTERESTS = ("culture", "food", "beaches", "family", "nightlife", "landmark")

# Off the 2026 holiday calendar. November mean high is 30.6 C, so the heat rule stays idle.
DEFAULT_START = date(2026, 11, 18)
EID_START = date(2026, 3, 19)
NATIONAL_START = date(2026, 12, 2)
# Luxury Old Dubai for 2 peak nights sits above this; the mid-tier swap falls under it.
BUDGET_FORCE_AED = 2200.0
EXHAUSTED_BUDGET_AED = 400.0


@dataclass(frozen=True)
class ParsedRequest:
    constraints: Constraints | None
    assumptions: list[str]
    force: str | None


# Longer phrases first so "Dubai Creek" is not read as a bare Dubai match.
_AREA_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bold dubai\b", re.IGNORECASE), "Old Dubai"),
    (re.compile(r"\bdubai creek\b", re.IGNORECASE), "Dubai Creek"),
    (re.compile(r"\bbusiness bay\b", re.IGNORECASE), "Business Bay"),
    (re.compile(r"\bal quoz\b", re.IGNORECASE), "Al Quoz"),
    (re.compile(r"\bjumeirah\b", re.IGNORECASE), "Jumeirah"),
    (re.compile(r"\bdowntown\b", re.IGNORECASE), "Downtown"),
    (re.compile(r"\bpalm\b", re.IGNORECASE), "Palm"),
    (re.compile(r"\bmarina\b|\bjbr\b", re.IGNORECASE), "Marina / JBR"),
)


def named_planning_areas(text: str) -> list[str]:
    """Planning areas named in the request. Bare 'Dubai' is not an area."""

    found: list[str] = []
    for pattern, area in _AREA_PATTERNS:
        if area in found:
            continue
        if pattern.search(text):
            found.append(area)
    return [area for area in found if area in PLANNING_AREAS]


def force_flag(text: str) -> str | None:
    match = _FORCE.search(text)
    if match is None:
        return None
    token = match.group(1).lower()
    if token == "national_day":
        return "national"
    return token


def parse_request_text(text: str) -> ParsedRequest:
    """Turn a short request into constraints. Missing trip length asks the user."""

    force = force_flag(text)
    assumptions: list[str] = []
    days = _days_in(text)
    budget = _budget_in(text)
    start = _start_in(text)
    tier = _tier_in(text)
    interests = _interests_in(text)
    avoid = bool(re.search(r"avoid\s+crowds", text, re.IGNORECASE))
    travelers = 1

    if force == "exhausted":
        days = 4
        budget = EXHAUSTED_BUDGET_AED
        start = start or DEFAULT_START
        tier = tier or "budget"
    elif force == "budget":
        days = days or 2
        budget = budget if budget is not None else BUDGET_FORCE_AED
        start = start or DEFAULT_START
        tier = "luxury"
    elif force == "eid":
        days = days or 2
        start = EID_START
        budget = budget if budget is not None else 8000.0
        tier = tier or "budget"
    elif force == "national":
        days = days or 2
        start = NATIONAL_START
        budget = budget if budget is not None else 8000.0
        tier = tier or "budget"
        avoid = True
    elif force == "museum":
        days = days or 2
        budget = budget if budget is not None else 8000.0
        start = start or DEFAULT_START
        tier = tier or "budget"
    elif days is None:
        return ParsedRequest(
            constraints=None,
            assumptions=["Trip length was not specified."],
            force=None,
        )

    if budget is None:
        budget = 5000.0
        assumptions.append("Budget defaulted to AED 5000 for the group, accommodation included.")
    if start is None:
        start = DEFAULT_START
        assumptions.append(
            f"Start date defaulted to {DEFAULT_START.isoformat()}, off the holiday calendar."
        )
    if tier is None:
        tier = "budget"
        assumptions.append("Hotel tier defaulted to budget (affordable).")
    if not interests:
        interests = ["culture", "food", "beaches"]
        assumptions.append("Interests defaulted to culture, food, and beaches.")
    assumptions.append("Flights are excluded. Pace is balanced. Travelers defaulted to 1.")
    if force:
        assumptions.append(f"Demo flag force:{force} is active.")

    constraints = Constraints(
        days=days,
        budget_aed=budget,
        budget_scope="total",
        travelers=travelers,
        excludes=["flights"],
        interests=interests,
        hotel_tier=tier,  # type: ignore[arg-type]
        avoid_crowds=avoid,
        pace="balanced",
        start_date=start,
    )
    return ParsedRequest(constraints=constraints, assumptions=assumptions, force=force)


def _days_in(text: str) -> int | None:
    match = _DAYS.search(text) or _DAYS_LABEL.search(text)
    if match is not None:
        return int(match.group(1))
    for line in text.splitlines():
        bare = _BARE_DAY.match(line)
        if bare is not None:
            return int(bare.group(1))
    return None


def _budget_in(text: str) -> float | None:
    match = _BUDGET.search(text)
    if match is None:
        return None
    return float(match.group(1))


def _start_in(text: str) -> date | None:
    match = _START.search(text)
    if match is None:
        return None
    return date.fromisoformat(match.group(1))


def _tier_in(text: str) -> str | None:
    lowered = text.lower()
    if re.search(r"\bluxury\b", lowered):
        return "luxury"
    if re.search(r"\bmid(?:-tier)?\b", lowered):
        return "mid"
    if re.search(r"\b(budget|affordable)\b", lowered):
        return "budget"
    return None


def _interests_in(text: str) -> list[str]:
    lowered = text.lower()
    found = [name for name in _INTERESTS if re.search(rf"\b{name}\b", lowered)]
    return found
