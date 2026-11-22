"""Optional cuisine and hours enrichment. Curated prices stay put."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from travel_planner.data.cache import Cache
from travel_planner.data.providers.attribution import OSM_ODBL, USER_AGENT
from travel_planner.data.providers.openrouteservice import _send
from travel_planner.data.resilience import ProviderHTTPError, SessionGuard, guarded_call

INTERPRETER = "https://overpass-api.de/api/interpreter"
TIMEOUT_SECONDS = 25
MAXSIZE_BYTES = 1_048_576
PER_MINUTE = 10


@dataclass(frozen=True)
class OsmTags:
    name: str
    cuisine: str | None
    opening_hours: str | None


class Overpass:
    def __init__(
        self,
        client: httpx.Client,
        guard: SessionGuard,
        cache: Cache,
        *,
        per_minute: int = PER_MINUTE,
    ) -> None:
        self.client = client
        self.guard = guard
        self.cache = cache
        self.per_minute = per_minute

    def restaurants_near(self, lat: float, lng: float, *, radius_m: int = 2500) -> list[OsmTags]:
        query = (
            f"[out:json][timeout:{TIMEOUT_SECONDS}][maxsize:{MAXSIZE_BYTES}];"
            f'node["amenity"="restaurant"](around:{radius_m},{lat},{lng});'
            "out tags;"
        )

        def call() -> list[OsmTags]:
            payload = _send(
                self.client,
                self.guard,
                "POST",
                INTERPRETER,
                headers={"User-Agent": USER_AGENT},
                data={"data": query},
                timeout=float(TIMEOUT_SECONDS),
            )
            return _parse(payload)

        return guarded_call(
            self.guard,
            self.cache,
            provider="overpass",
            per_minute=self.per_minute,
            quota="overpass",
            quota_limit=2000,
            fn=call,
        )


def _parse(payload: dict) -> list[OsmTags]:
    elements = payload.get("elements")
    if not isinstance(elements, list):
        raise ProviderHTTPError(502, "Overpass response has no elements")
    rows: list[OsmTags] = []
    for element in elements:
        tags = element.get("tags") if isinstance(element, dict) else None
        if not isinstance(tags, dict):
            continue
        name = str(tags.get("name") or "").strip()
        if not name:
            continue
        cuisine = tags.get("cuisine")
        hours = tags.get("opening_hours")
        rows.append(
            OsmTags(
                name=name,
                cuisine=str(cuisine).strip() if cuisine else None,
                opening_hours=str(hours).strip() if hours else None,
            )
        )
    return rows


def attribution() -> str:
    return OSM_ODBL
