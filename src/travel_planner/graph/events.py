"""Agent events emitted by every graph node."""

from datetime import UTC, datetime

from langgraph.config import get_stream_writer

from travel_planner.models import AgentEvent


def make_event(
    node: str,
    phase: str,
    summary: str,
    delta: dict[str, object] | None = None,
    duration_ms: int | None = None,
    tokens: dict[str, int] | None = None,
) -> AgentEvent:
    return AgentEvent(
        ts=datetime.now(UTC),
        node=node,
        phase=phase,  # type: ignore[arg-type]
        summary=summary,
        state_delta=delta or {},
        duration_ms=duration_ms,
        tokens=tokens,
    )


def publish(event: AgentEvent) -> None:
    """Push an event onto the custom stream when a run is active."""

    try:
        get_stream_writer()(event)
    except RuntimeError:
        return
