"""Interrupt until the caller supplies the missing trip length."""

from langgraph.types import interrupt

from travel_planner.graph.context import NodeContext
from travel_planner.state import TripState

_QUESTION = "How many days should the trip be (1-7)?"


def ask_user(state: TripState, ctx: NodeContext) -> dict[str, object]:
    _ = ctx
    answer = interrupt({"missing": ["days"], "question": _QUESTION})
    addition = answer.get("text") if isinstance(answer, dict) else answer
    combined = f"{state['raw_request'].rstrip()}\n{addition}".strip()
    return {
        "raw_request": combined,
        "_summary": "Clarification appended to the request.",
        "_delta": {"resume": str(addition)},
    }
