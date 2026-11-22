"""Public OSRM demo. Light use only, after OpenRouteService misses."""

from __future__ import annotations

import httpx

from travel_planner.data.cache import Cache
from travel_planner.data.providers.attribution import OSM_ODBL, USER_AGENT
from travel_planner.data.providers.openrouteservice import Point, RoadRoute, _send
from travel_planner.data.resilience import ProviderHTTPError, SessionGuard, guarded_call

DEMO_URL = "https://router.project-osrm.org/route/v1/{profile}/{coords}"
PER_MINUTE = 30


class Osrm:
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

    def route(self, origin: Point, dest: Point, *, profile: str = "driving") -> RoadRoute:
        def call() -> RoadRoute:
            coords = f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
            payload = _send(
                self.client,
                self.guard,
                "GET",
                DEMO_URL.format(profile=profile, coords=coords),
                headers={"User-Agent": USER_AGENT},
                params={"overview": "false"},
            )
            if payload.get("code") != "Ok":
                raise ProviderHTTPError(502, "OSRM demo did not return a route")
            routes = payload.get("routes") or []
            if not routes:
                raise ProviderHTTPError(502, "OSRM demo returned no route")
            leg = routes[0]
            return RoadRoute(
                minutes=max(1, round(float(leg["duration"]) / 60)),
                distance_km=round(float(leg["distance"]) / 1000, 3),
                provider="osrm",
                attribution=OSM_ODBL,
            )

        return guarded_call(
            self.guard,
            self.cache,
            provider="osrm",
            per_minute=self.per_minute,
            quota="osrm-routes",
            quota_limit=2000,
            fn=call,
        )
