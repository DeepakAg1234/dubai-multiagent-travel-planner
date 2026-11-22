"""OpenRouteService directions and matrix. The API key stays optional."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from travel_planner.data.cache import Cache
from travel_planner.data.providers.attribution import OSM_ODBL, USER_AGENT
from travel_planner.data.resilience import (
    BudgetExhausted,
    ProviderHTTPError,
    SessionGuard,
    guarded_call,
)

DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/{profile}"
MATRIX_URL = "https://api.openrouteservice.org/v2/matrix/{profile}"
PER_MINUTE = 40
DIRECTIONS_DAILY = 2000
MATRIX_DAILY = 500
Point = tuple[float, float]


@dataclass(frozen=True)
class RoadRoute:
    minutes: int
    distance_km: float
    provider: str
    attribution: str = OSM_ODBL


class OpenRouteService:
    def __init__(
        self,
        api_key: str,
        client: httpx.Client,
        guard: SessionGuard,
        cache: Cache,
        *,
        per_minute: int = PER_MINUTE,
        directions_daily: int = DIRECTIONS_DAILY,
        matrix_daily: int = MATRIX_DAILY,
    ) -> None:
        self.api_key = api_key.strip()
        self.client = client
        self.guard = guard
        self.cache = cache
        self.per_minute = per_minute
        self.directions_daily = directions_daily
        self.matrix_daily = matrix_daily

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def directions(
        self,
        origin: Point,
        dest: Point,
        *,
        profile: str = "driving-car",
    ) -> RoadRoute:
        if not self.enabled:
            raise ProviderHTTPError(401, "ORS_API_KEY is empty")

        def call() -> RoadRoute:
            payload = _send(
                self.client,
                self.guard,
                "POST",
                DIRECTIONS_URL.format(profile=profile),
                headers={"Authorization": self.api_key, "User-Agent": USER_AGENT},
                json={"coordinates": [[origin[1], origin[0]], [dest[1], dest[0]]]},
            )
            return _parse_directions(payload)

        return guarded_call(
            self.guard,
            self.cache,
            provider="openrouteservice",
            per_minute=self.per_minute,
            quota="ors-directions",
            quota_limit=self.directions_daily,
            fn=call,
        )

    def matrix(
        self,
        points: list[Point],
        *,
        profile: str = "driving-car",
    ) -> list[list[float | None]]:
        if not self.enabled:
            raise ProviderHTTPError(401, "ORS_API_KEY is empty")
        if len(points) > 50:
            raise ProviderHTTPError(400, "matrix is limited to 50 locations")

        def call() -> list[list[float | None]]:
            payload = _send(
                self.client,
                self.guard,
                "POST",
                MATRIX_URL.format(profile=profile),
                headers={"Authorization": self.api_key, "User-Agent": USER_AGENT},
                json={
                    "locations": [[lng, lat] for lat, lng in points],
                    "metrics": ["duration", "distance"],
                },
            )
            return _parse_matrix(payload)

        return guarded_call(
            self.guard,
            self.cache,
            provider="openrouteservice",
            per_minute=self.per_minute,
            quota="ors-matrix",
            quota_limit=self.matrix_daily,
            fn=call,
        )


def _parse_directions(payload: dict) -> RoadRoute:
    routes = payload.get("routes") or []
    if not routes:
        raise ProviderHTTPError(502, "OpenRouteService returned no route")
    summary = routes[0].get("summary") or {}
    if "duration" not in summary or "distance" not in summary:
        raise ProviderHTTPError(502, "OpenRouteService summary is missing duration")
    return RoadRoute(
        minutes=max(1, round(float(summary["duration"]) / 60)),
        distance_km=round(float(summary["distance"]) / 1000, 3),
        provider="openrouteservice",
    )


def _parse_matrix(payload: dict) -> list[list[float | None]]:
    durations = payload.get("durations")
    if not isinstance(durations, list):
        raise ProviderHTTPError(502, "OpenRouteService matrix is missing durations")
    grid: list[list[float | None]] = []
    for row in durations:
        parsed: list[float | None] = []
        for value in row:
            if value is None:
                parsed.append(None)
            else:
                parsed.append(round(float(value) / 60, 1))
        grid.append(parsed)
    return grid


def _send(
    client: httpx.Client,
    guard: SessionGuard,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json: dict | None = None,
    data: dict | None = None,
    params: dict | None = None,
    timeout: float = 8.0,
) -> dict:
    if not guard.try_spend():
        raise BudgetExhausted("api call budget is exhausted")
    try:
        response = client.request(
            method,
            url,
            headers=headers,
            json=json,
            data=data,
            params=params,
            timeout=timeout,
        )
    except httpx.TimeoutException as exc:
        raise ProviderHTTPError(408, "timeout") from exc
    except httpx.HTTPError as exc:
        raise ProviderHTTPError(503, str(exc)) from exc
    if response.status_code >= 400:
        raise ProviderHTTPError(response.status_code, response.text[:200])
    body = response.json()
    if not isinstance(body, dict):
        raise ProviderHTTPError(502, "provider response was not an object")
    return body
