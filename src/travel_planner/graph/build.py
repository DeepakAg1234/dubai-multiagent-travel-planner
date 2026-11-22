"""Assemble the planner StateGraph.

Fan-out after the orchestrator is the join: logistics_sequence waits until
destination research and preliminary logistics have both written their keys.
The checkpointer is in-memory for one local run. Durable resume stays off
unless a later phase configures CHECKPOINT_STORE_URL.
"""

from datetime import date

import httpx
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import TracePolicy

from travel_planner import models as model_pkg
from travel_planner.config import Settings
from travel_planner.data.local.sqlite import SqliteCatalog
from travel_planner.graph.context import NodeContext
from travel_planner.graph.nodes.ask_user import ask_user
from travel_planner.graph.nodes.budget import budget, budget_adjust
from travel_planner.graph.nodes.finalize import finalize
from travel_planner.graph.nodes.logistics import logistics_prelim, logistics_sequence
from travel_planner.graph.nodes.orchestrator import orchestrator_plan, orchestrator_revise
from travel_planner.graph.nodes.parse_request import parse_request
from travel_planner.graph.nodes.research import destination_research
from travel_planner.graph.nodes.review import review
from travel_planner.graph.routing import bind_review_route, route_after_parse
from travel_planner.graph.trace import traced
from travel_planner.log import trace_inputs, trace_outputs
from travel_planner.state import TripState
from travel_planner.structured import ChatFn, UsageLedger
from travel_planner.tools.catalog import CatalogTools

NODE_TIMEOUT_SECONDS = 30.0

_TOOLS: dict[int, CatalogTools] = {}


def catalog_tools(graph: object) -> CatalogTools:
    """The catalog closed over by ``graph``. Nodes share this instance."""

    return _TOOLS[id(graph)]


def build_graph(
    catalog: SqliteCatalog,
    settings: Settings,
    ledger: UsageLedger | None = None,
    *,
    client: httpx.Client | None = None,
    today: date | None = None,
    chat: ChatFn | None = None,
):
    ctx = NodeContext(
        tools=CatalogTools(catalog, settings=settings, client=client, today=today),
        settings=settings,
        ledger=ledger or UsageLedger(),
        chat=chat,
    )
    graph: StateGraph = StateGraph(TripState)
    trace = TracePolicy(process_inputs=trace_inputs, process_outputs=trace_outputs)

    def add(name: str, fn) -> None:
        graph.add_node(
            name,
            traced(name, lambda state, fn=fn: fn(state, ctx)),
            timeout=NODE_TIMEOUT_SECONDS,
            trace_policy=trace,
        )

    add("parse_request", parse_request)
    add("ask_user", ask_user)
    add("orchestrator_plan", orchestrator_plan)
    add("destination_research", destination_research)
    add("logistics_prelim", logistics_prelim)
    add("logistics_sequence", logistics_sequence)
    add("budget", budget)
    add("review", review)
    add("budget_adjust", budget_adjust)
    add("orchestrator_revise", orchestrator_revise)
    add("finalize", finalize)

    graph.add_edge(START, "parse_request")
    graph.add_conditional_edges(
        "parse_request",
        route_after_parse,
        {"ask_user": "ask_user", "orchestrator_plan": "orchestrator_plan"},
    )
    graph.add_edge("ask_user", "parse_request")
    graph.add_edge("orchestrator_plan", "destination_research")
    graph.add_edge("orchestrator_plan", "logistics_prelim")
    graph.add_edge("destination_research", "logistics_sequence")
    graph.add_edge("logistics_prelim", "logistics_sequence")
    graph.add_edge("logistics_sequence", "budget")
    graph.add_edge("budget", "review")
    graph.add_conditional_edges(
        "review",
        bind_review_route(settings.max_revisions),
        {
            "finalize": "finalize",
            "budget_adjust": "budget_adjust",
            "orchestrator_revise": "orchestrator_revise",
        },
    )
    graph.add_edge("budget_adjust", "budget")
    graph.add_edge("orchestrator_revise", "destination_research")
    graph.add_edge("orchestrator_revise", "logistics_prelim")
    graph.add_edge("finalize", END)
    serde = JsonPlusSerializer(allowed_msgpack_modules=_model_allowlist())
    compiled = graph.compile(checkpointer=MemorySaver(serde=serde))
    _TOOLS[id(compiled)] = ctx.tools
    return compiled


def _model_allowlist() -> list[tuple[str, str]]:
    """Checkpoint serde may revive these Pydantic models and nothing else."""

    allowed: list[tuple[str, str]] = []
    for module in (model_pkg.catalog, model_pkg.common, model_pkg.trip):
        for value in vars(module).values():
            if isinstance(value, type) and value.__module__.startswith("travel_planner.models"):
                allowed.append((value.__module__, value.__name__))
    return allowed
