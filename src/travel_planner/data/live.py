"""Cache, then live API, then the caller falls back to the catalog."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date

import httpx

from travel_planner.config import Settings
from travel_planner.data.cache import (
    PLACES_TTL_SECONDS,
    ROUTES_TTL_SECONDS,
    WEATHER_TTL_SECONDS,
    Cache,
    cache_key,
)
from travel_planner.data.providers.attribution import OSM_ODBL, USER_AGENT
from travel_planner.data.providers.open_meteo import ForecastOutOfRange, OpenMeteo
from travel_planner.data.providers.openrouteservice import OpenRouteService, Point, RoadRoute
from travel_planner.data.providers.osrm import Osrm
from travel_planner.data.providers.overpass import OsmTags, Overpass
from travel_planner.data.resilience import (
    BudgetExhausted,
    CircuitOpen,
    ProviderHTTPError,
    QuotaExceeded,
    RateLimited,
    SessionGuard,
)
from travel_planner.models import ClimateMonth, Restaurant
from travel_planner.rules.hours import parse_window

_LIVE_ERRORS = (
    CircuitOpen,
    RateLimited,
    BudgetExhausted,
    QuotaExceeded,
    ProviderHTTPError,
)


class LiveResolver:
    def __init__(
        self,
        settings: Settings,
        cache: Cache,
        guard: SessionGuard,
        *,
        client: httpx.Client | None = None,
        today: date | None = None,
    ) -> None:
        self.cache = cache
        self.guard = guard
        self.last_error: str | None = None
        self._today = today
        self.client = client or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30.0)
        self.ors = OpenRouteService(settings.ors_api_key, self.client, guard, cache)
        self.osrm = Osrm(self.client, guard, cache)
        self.overpass = Overpass(self.client, guard, cache)
        self.meteo = OpenMeteo(self.client, guard, cache)

    def today(self) -> date:
        if self._today is not None:
            return self._today
        return self.guard.today()

    def road(self, origin: Point, dest: Point) -> tuple[RoadRoute, bool] | None:
        """A live road leg, and whether a lower provider had to stand in."""

        self.last_error = None
        key = cache_key(
            "route",
            {
                "origin": [round(origin[0], 4), round(origin[1], 4)],
                "dest": [round(dest[0], 4), round(dest[1], 4)],
            },
        )
        cached = self._load_route(key)
        if cached is not None:
            return cached
        errors: list[str] = []
        if self.ors.enabled:
            try:
                route = self.ors.directions(origin, dest)
            except _LIVE_ERRORS as exc:
                errors.append(str(exc))
            else:
                self._store_route(key, route, degraded=False)
                return route, False
        try:
            route = self.osrm.route(origin, dest)
        except _LIVE_ERRORS as exc:
            errors.append(str(exc))
            self.last_error = "; ".join(errors) or str(exc)
            return None
        degraded = bool(errors)
        self._store_route(key, route, degraded=degraded)
        return route, degraded

    def matrix(self, points: list[Point]) -> list[list[float | None]] | None:
        self.last_error = None
        if not self.ors.enabled:
            self.last_error = "ORS_API_KEY is empty"
            return None
        key = cache_key(
            "route-matrix",
            [[round(lat, 4), round(lng, 4)] for lat, lng in points],
        )
        cached = self.cache.get(key)
        if cached is not None:
            return json.loads(cached)
        try:
            grid = self.ors.matrix(points)
        except _LIVE_ERRORS as exc:
            self.last_error = str(exc)
            return None
        self.cache.set(key, json.dumps(grid), ROUTES_TTL_SECONDS)
        return grid

    def forecast(self, day: date) -> ClimateMonth | None:
        self.last_error = None
        key = cache_key("weather", {"day": day.isoformat()})
        cached = self.cache.get(key)
        if cached is not None:
            return ClimateMonth.model_validate_json(cached)
        try:
            daily = self.meteo.forecast(day, today=self.today())
        except ForecastOutOfRange as exc:
            self.last_error = str(exc)
            return None
        except _LIVE_ERRORS as exc:
            self.last_error = str(exc)
            return None
        month = ClimateMonth(
            month=day.month,
            avg_high_c=daily.high_c,
            avg_low_c=daily.low_c,
            rain_mm=daily.rain_mm,
            humidity_pct=daily.humidity_pct,
            provenance="api",
            source=daily.source,
            as_of=day,
        )
        self.cache.set(key, month.model_dump_json(), WEATHER_TTL_SECONDS)
        return month

    def enrich_restaurants(
        self,
        area: str,
        rows: list[Restaurant],
    ) -> tuple[list[Restaurant], bool, str | None]:
        """Fill cuisine and hours. Prices, bands, and meal types stay curated."""

        self.last_error = None
        if not rows:
            return rows, False, None
        lat = sum(row.lat for row in rows) / len(rows)
        lng = sum(row.lng for row in rows) / len(rows)
        key = cache_key(
            "places",
            {"area": area, "lat": round(lat, 3), "lng": round(lng, 3)},
        )
        cached = self.cache.get(key)
        if cached is not None:
            tags = [OsmTags(**item) for item in json.loads(cached)]
            return _apply_tags(rows, tags), False, None
        try:
            tags = self.overpass.restaurants_near(lat, lng)
        except _LIVE_ERRORS as exc:
            self.last_error = str(exc)
            return rows, True, str(exc)
        self.cache.set(
            key,
            json.dumps([asdict(tag) for tag in tags]),
            PLACES_TTL_SECONDS,
        )
        return _apply_tags(rows, tags), False, None

    def _load_route(self, key: str) -> tuple[RoadRoute, bool] | None:
        raw = self.cache.get(key)
        if raw is None:
            return None
        payload = json.loads(raw)
        route = RoadRoute(
            minutes=int(payload["minutes"]),
            distance_km=float(payload["distance_km"]),
            provider=str(payload["provider"]),
            attribution=str(payload.get("attribution") or OSM_ODBL),
        )
        return route, bool(payload.get("degraded"))

    def _store_route(self, key: str, route: RoadRoute, *, degraded: bool) -> None:
        payload = {
            "minutes": route.minutes,
            "distance_km": route.distance_km,
            "provider": route.provider,
            "attribution": route.attribution,
            "degraded": degraded,
        }
        self.cache.set(key, json.dumps(payload), ROUTES_TTL_SECONDS)


def _apply_tags(
    rows: list[Restaurant],
    tags: list[OsmTags],
) -> list[Restaurant]:
    updated: list[Restaurant] = []
    for row in rows:
        tag = _match(row.name, tags)
        if tag is None:
            updated.append(row)
            continue
        changes: dict[str, object] = {}
        if row.cuisine == "unspecified" and tag.cuisine:
            changes["cuisine"] = tag.cuisine
        if tag.opening_hours and parse_window(tag.opening_hours) is not None:
            changes["opening_hours"] = {"daily": tag.opening_hours}
        if not changes:
            updated.append(row)
            continue
        changes["source"] = f"{row.source}; Overpass; {OSM_ODBL}"
        updated.append(row.model_copy(update=changes))
    return updated


def _match(name: str, tags: list[OsmTags]) -> OsmTags | None:
    wanted = _norm(name)
    if not wanted:
        return None
    for tag in tags:
        found = _norm(tag.name)
        if not found:
            continue
        if found == wanted or (len(found) >= 6 and (found in wanted or wanted in found)):
            return tag
    return None


def _norm(name: str) -> str:
    return "".join(char for char in name.casefold() if char.isalnum())
