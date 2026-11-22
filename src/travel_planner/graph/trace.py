"""Wrap a node so it always records a start event and an end or error event.

Nodes are async so LangGraph can apply the per-node timeout. The stub work
itself stays synchronous and runs on the graph task, which keeps interrupts
in the same context.
"""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

from langgraph.errors import GraphInterrupt

from travel_planner.graph.events import make_event, publish
from travel_planner.state import TripState

NodeFn = Callable[[TripState], dict[str, object]]


def traced(name: str, fn: NodeFn):
    async def node(state: TripState) -> dict[str, object]:
        started = perf_counter()
        start = make_event(name, "start", f"{name} started")
        publish(start)
        try:
            raw = fn(state)
        except GraphInterrupt:
            raise
        except Exception as exc:
            error = make_event(name, "error", f"{name} failed: {exc}")
            publish(error)
            raise
        summary = str(raw.pop("_summary", f"{name} finished"))
        delta = raw.pop("_delta", {})
        extra = list(raw.pop("events", []))  # type: ignore[arg-type]
        tokens = raw.pop("_tokens", None)
        duration_ms = int((perf_counter() - started) * 1000)
        end = make_event(
            name,
            "end",
            summary,
            delta if isinstance(delta, dict) else {},
            duration_ms,
            tokens if isinstance(tokens, dict) else None,
        )
        publish(end)
        raw["events"] = [start, *extra, end]
        return raw

    return node
