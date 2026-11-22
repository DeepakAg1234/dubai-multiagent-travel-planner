"""Planner service boundary.

`run` yields `AgentEvent` values. Callers never see LangGraph state, commands,
or checkpoint types.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from datetime import date
from threading import Lock
from uuid import uuid4

import httpx
from langgraph.errors import GraphInterrupt, GraphRecursionError, NodeTimeoutError
from langgraph.types import Command

from travel_planner.audit import AuditReport, audit_itinerary
from travel_planner.config import Settings, get_settings
from travel_planner.data.local.sqlite import SqliteCatalog
from travel_planner.graph.build import build_graph, catalog_tools
from travel_planner.graph.events import make_event
from travel_planner.log import configure_logging, get_logger, tracing_requested
from travel_planner.models import AgentEvent
from travel_planner.present import present_state, usage_delta
from travel_planner.state import TripState
from travel_planner.structured import ChatFn, UsageLedger
from travel_planner.tools.catalog import CatalogTools

CheckpointFn = Callable[[str, dict[str, object]], None]

RECURSION_LIMIT = 80


class PlannerService:
    def __init__(
        self,
        settings: Settings | None = None,
        catalog: SqliteCatalog | None = None,
        *,
        client: httpx.Client | None = None,
        today: date | None = None,
        chat: ChatFn | None = None,
    ) -> None:
        configure_logging()
        self.settings = settings or get_settings()
        self.usage = UsageLedger()
        if catalog is not None:
            self._catalog = catalog
        else:
            path = self.settings.sqlite_path
            if not path.is_file():
                raise FileNotFoundError(
                    f"Curated database not found at {path}. Run python scripts/build_db.py."
                )
            self._catalog = SqliteCatalog(path)
        self._graph = build_graph(
            self._catalog,
            self.settings,
            self.usage,
            client=client,
            today=today,
            chat=chat,
        )
        self._lock = Lock()
        self._usage_by_thread: dict[str, dict[str, dict[str, int]]] = {}

    def run(
        self,
        request: str,
        *,
        thread_id: str | None = None,
        resume: object | None = None,
        use_live_apis: bool | None = None,
        on_checkpoint: CheckpointFn | None = None,
        recursion_limit: int = RECURSION_LIMIT,
    ) -> Iterator[AgentEvent]:
        """Yield agent events. ``on_checkpoint`` fires after each node commits."""

        thread = thread_id or str(uuid4())

        def _generate() -> Iterator[AgentEvent]:
            with self._lock:
                tools = catalog_tools(self._graph)
                enabled = self.settings.use_live_apis if use_live_apis is None else use_live_apis
                tools.set_live_apis(enabled)
                usage_before = self.usage.snapshot()
                try:
                    get_logger().info(
                        "planner run started chars=%s live_apis=%s thread=%s",
                        len(request),
                        enabled,
                        thread,
                    )
                    if tracing_requested():
                        get_logger().info(
                            "LangSmith tracing is enabled. Node traces record request length only."
                        )
                    yield from self._stream(
                        request,
                        thread,
                        resume=resume,
                        on_checkpoint=on_checkpoint,
                        usage_before=usage_before,
                        recursion_limit=recursion_limit,
                    )
                finally:
                    self._usage_by_thread[thread] = usage_delta(
                        usage_before,
                        self.usage.snapshot(),
                    )
                    tools.set_live_apis(self.settings.use_live_apis)

        return _generate()

    def _stream(
        self,
        request: str,
        thread: str,
        *,
        resume: object | None,
        on_checkpoint: CheckpointFn | None,
        usage_before: dict[str, dict[str, int]],
        recursion_limit: int,
    ) -> Iterator[AgentEvent]:
        config = {
            "configurable": {"thread_id": thread},
            "recursion_limit": recursion_limit,
        }
        incoming: dict | Command = Command(resume=resume) if resume is not None else _blank(request)
        seen_ask = False
        agen = self._graph.astream(
            incoming,
            config,
            stream_mode=["updates", "custom"],
        )
        loop = asyncio.new_event_loop()
        try:
            while True:
                try:
                    item = loop.run_until_complete(agen.__anext__())
                except StopAsyncIteration:
                    break
                mode, payload = _unpack(item)
                if mode == "custom":
                    event = _as_event(payload)
                    if event is None:
                        continue
                    if event.node == "ask_user" and event.phase == "start":
                        seen_ask = True
                    yield event
                    continue
                if mode == "updates" and isinstance(payload, dict):
                    if "__interrupt__" in payload:
                        self._remember(thread, "ask_user", on_checkpoint, usage_before)
                        if not seen_ask:
                            yield make_event(
                                "ask_user",
                                "start",
                                "Waiting for the missing trip length.",
                                {"missing": ["days"]},
                            )
                            seen_ask = True
                        continue
                    node = next(iter(payload), "")
                    self._remember(thread, str(node), on_checkpoint, usage_before)
        except GraphInterrupt:
            self._remember(thread, "ask_user", on_checkpoint, usage_before)
            if not seen_ask:
                yield make_event(
                    "ask_user",
                    "start",
                    "Waiting for the missing trip length.",
                    {"missing": ["days"]},
                )
        except (GraphRecursionError, NodeTimeoutError) as exc:
            get_logger().warning("planner hard stop: %s", type(exc).__name__)
            yield make_event(
                "planner",
                "error",
                _hard_stop_summary(exc),
                {"stopped": type(exc).__name__},
            )
        finally:
            loop.close()

    def _remember(
        self,
        thread: str,
        node: str,
        on_checkpoint: CheckpointFn | None,
        usage_before: dict[str, dict[str, int]],
    ) -> None:
        usage = usage_delta(usage_before, self.usage.snapshot())
        self._usage_by_thread[thread] = usage
        if on_checkpoint is None:
            return
        on_checkpoint(node, self.snapshot(thread))

    def values(self, thread_id: str) -> dict[str, object]:
        snapshot = self._graph.get_state({"configurable": {"thread_id": thread_id}})
        return dict(snapshot.values)

    def interrupts(self, thread_id: str) -> list[dict[str, object]]:
        snapshot = self._graph.get_state({"configurable": {"thread_id": thread_id}})
        pending: list[dict[str, object]] = []
        for item in snapshot.interrupts:
            value = item.value
            if isinstance(value, dict):
                pending.append(value)
            else:
                pending.append({"value": value})
        return pending

    def snapshot(self, thread_id: str) -> dict[str, object]:
        usage = self._usage_by_thread.get(thread_id, {})
        return present_state(self.values(thread_id), catalog_tools(self._graph), usage)

    def mermaid(self) -> str:
        return self._graph.get_graph().draw_mermaid()

    def audit(self, text: str) -> AuditReport:
        """Check a pasted itinerary. Does not start a LangGraph run."""

        tools = self.tools
        return audit_itinerary(
            text,
            places=tools.places,
            restaurants=tools.restaurants,
            hotels=tools.hotels,
            stations=tools.stations,
            edges=tools.edges,
            fares=tools.fares,
            bands=tools.bands,
            holidays=tools.holidays,
            climate=tools.climate,
            buffer_pct=self.settings.buffer_pct,
        )

    @property
    def tools(self) -> CatalogTools:
        return catalog_tools(self._graph)


def _blank(request: str) -> TripState:
    return {
        "raw_request": request,
        "constraints": None,
        "assumptions": [],
        "plan_brief": None,
        "candidates": None,
        "stay_options": [],
        "transport_options": [],
        "draft_itinerary": None,
        "budget_report": None,
        "review_report": None,
        "revision_count": 0,
        "excluded_ids": [],
        "events": [],
        "warnings": [],
        "final_itinerary": None,
    }


def _unpack(item: object) -> tuple[str, object]:
    if isinstance(item, tuple) and len(item) == 2 and item[0] in {"updates", "custom"}:
        return str(item[0]), item[1]
    return "", item


def _hard_stop_summary(exc: GraphRecursionError | NodeTimeoutError) -> str:
    if isinstance(exc, GraphRecursionError):
        return "Recursion limit reached. The run stopped before another revision."
    return (
        f"{exc.node} exceeded its {exc.timeout:g}s timeout. "
        "The run stopped and did not continue the revision loop."
    )


def _as_event(payload: object) -> AgentEvent | None:
    if isinstance(payload, AgentEvent):
        return payload
    if isinstance(payload, dict) and "node" in payload and "phase" in payload:
        return AgentEvent.model_validate(payload)
    return None
