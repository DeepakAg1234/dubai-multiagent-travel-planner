"""Shared grounding checks and the per-node structured call."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import timedelta

from pydantic import BaseModel

from travel_planner.data.areas import PLANNING_AREAS
from travel_planner.graph.context import NodeContext
from travel_planner.llm import node_llm_enabled
from travel_planner.models import Constraints, Holiday, Place, PlanBrief
from travel_planner.rules.holidays import effects_on
from travel_planner.structured import LlmOutcome, complete

_HERITAGE = ("museum", "mosque", "gallery")
_CROWD = (
    "mall",
    "beach",
    "theme park",
    "water park",
    "viewpoint",
    "landmark",
    "park",
)
_CLOSE = "<<</UNTRUSTED>>>"


def resolve_chat(node: str, ctx: NodeContext):
    if ctx.chat_for is not None:
        bound = ctx.chat_for(node)
        if bound is not None:
            return bound
    return ctx.chat


def llm_active(node: str, ctx: NodeContext) -> bool:
    """True when a test injected a chat function or the provider key is set."""

    return resolve_chat(node, ctx) is not None or node_llm_enabled(node, ctx.settings)


def ask[T: BaseModel](
    node: str,
    schema: type[T],
    data: str,
    ctx: NodeContext,
    fallback: Callable[[], T],
    check: Callable[[T], str | None] | None = None,
) -> LlmOutcome[T]:
    return complete(
        node,
        schema,
        data,
        settings=ctx.settings,
        fallback=fallback,
        chat=resolve_chat(node, ctx),
        ledger=ctx.ledger,
        check=check,
    )


def with_tokens(outcome: LlmOutcome[object], payload: dict[str, object]) -> dict[str, object]:
    tokens = outcome.tokens()
    if tokens is not None:
        payload["_tokens"] = tokens
    return payload


def untrusted(record_id: str, source: str) -> str:
    """Wrap catalog source text so a model cannot treat it as instructions."""

    body = source.replace(_CLOSE, "").replace("<<<UNTRUSTED", "")
    clipped = body[:400]
    return f'<<<UNTRUSTED id="{record_id}">>>\n{clipped}\n{_CLOSE}'


def known_areas(places: list[Place]) -> list[str]:
    extra = sorted({place.area for place in places if place.area not in PLANNING_AREAS})
    return [*PLANNING_AREAS, *extra]


def theme_allowed(
    theme: str,
    day_index: int,
    constraints: Constraints,
    holidays: list[Holiday],
) -> bool:
    """Reject heritage themes on Eid day one and crowd themes on high-crowd days."""

    if constraints.start_date is None:
        return True
    day = constraints.start_date + timedelta(days=day_index - 1)
    effects = effects_on(holidays, day)
    if effects is None:
        return True
    if effects.heritage_may_close and _mentions(theme, _HERITAGE):
        return False
    if effects.high_crowd and constraints.avoid_crowds and _mentions(theme, _CROWD):
        return False
    return True


def brief_allowed(
    brief: PlanBrief,
    constraints: Constraints,
    holidays: list[Holiday],
    areas: set[str],
) -> str | None:
    if len(brief.days) != constraints.days:
        return f"expected {constraints.days} days"
    for day in brief.days:
        if not day.areas or any(area not in areas for area in day.areas):
            return f"day {day.day} uses an area outside the catalog"
        if not theme_allowed(day.theme, day.day, constraints, holidays):
            return f"day {day.day} theme conflicts with the holiday calendar"
    focus = [item.lower() for item in brief.cuisine_focus]
    if any(item not in {"local", "area food"} for item in focus):
        return "cuisine_focus must be empty or local; restaurant cuisine is unspecified"
    return None


def provenance_lines(places: list[Place], station_provenance: list[str]) -> list[str]:
    verified = [place.name for place in places if place.provenance == "verified"]
    verified_name = verified[0] if len(verified) == 1 else "Dubai Frame"
    api_count = sum(1 for item in station_provenance if item == "api")
    total = len(station_provenance)
    return [
        "Place, hotel, restaurant, and climate figures are estimated unless a line says otherwise.",
        f"{verified_name}'s adult ticket is the only verified place price.",
        f"{api_count} of {total} transit stations are provenance api.",
    ]


def _mentions(theme: str, words: tuple[str, ...]) -> bool:
    lowered = theme.lower()
    return any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in words)
