"""Dependencies closed over by graph nodes. They are not part of TripState."""

from collections.abc import Callable
from dataclasses import dataclass, field

from travel_planner.config import Settings
from travel_planner.structured import ChatFn, UsageLedger
from travel_planner.tools.catalog import CatalogTools


@dataclass(frozen=True)
class NodeContext:
    tools: CatalogTools
    settings: Settings
    ledger: UsageLedger = field(default_factory=UsageLedger)
    chat: ChatFn | None = None
    chat_for: Callable[[str], ChatFn | None] | None = None
