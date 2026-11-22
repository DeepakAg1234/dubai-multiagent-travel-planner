"""Agent-facing tools.

Resolution order is cache, then a live API when ``USE_LIVE_APIS`` is on and
the provider is healthy, then the curated catalog. A fallback sets
``degraded``. Attractions and hotels stay on the catalog.
"""

from __future__ import annotations

from datetime import date, time

import httpx

from travel_planner.config import Settings
from travel_planner.data.cache import Cache, open_cache
from travel_planner.data.live import LiveResolver
from travel_planner.data.local.sqlite import SqliteCatalog
from travel_planner.data.providers.attribution import OSM_ODBL
from travel_planner.data.resilience import SessionGuard
from travel_planner.models import (
    ClimateMonth,
    Fare,
    Holiday,
    Hotel,
    Leg,
    Place,
    PriceBand,
    Restaurant,
    TransitEdge,
    TransitStation,
    TransportOption,
)
from travel_planner.models.common import ToolResult
from travel_planner.rules.fares import (
    TransitGraph,
    abra_fare,
    route_leg,
    silver_metro_fare,
    taxi_fare_aed,
)

_SOURCE = "data/dubai.sqlite"


class CatalogTools:
    """In-memory view loaded once so parallel nodes do not share a connection."""

    def __init__(
        self,
        catalog: SqliteCatalog,
        *,
        settings: Settings | None = None,
        client: httpx.Client | None = None,
        cache: Cache | None = None,
        guard: SessionGuard | None = None,
        today: date | None = None,
    ) -> None:
        from travel_planner.data.local.sqlite import (
            SqliteClimateRepo,
            SqliteFareRepo,
            SqliteHolidayRepo,
            SqliteHotelRepo,
            SqlitePlaceRepo,
            SqlitePriceRepo,
            SqliteRestaurantRepo,
            SqliteTransitRepo,
        )

        self.places: list[Place] = SqlitePlaceRepo(catalog).search()
        self.restaurants: list[Restaurant] = SqliteRestaurantRepo(catalog).search()
        self.hotels: list[Hotel] = SqliteHotelRepo(catalog).search()
        self.stations: list[TransitStation] = SqliteTransitRepo(catalog).stations()
        self.edges: list[TransitEdge] = SqliteTransitRepo(catalog).edges()
        self.fares: list[Fare] = SqliteFareRepo(catalog).all()
        self.bands: list[PriceBand] = SqlitePriceRepo(catalog).bands()
        self.climate: list[ClimateMonth] = SqliteClimateRepo(catalog).all()
        self.holidays: list[Holiday] = SqliteHolidayRepo(catalog).all()
        self.graph = TransitGraph(self.stations, self.edges)
        self._settings = settings
        self._client = client
        self._cache = cache
        self._guard = guard
        self._today = today
        self._suppress_live = False
        self._live = _live_stack(settings, client=client, cache=cache, guard=guard, today=today)
        self._place_by_id = {row.id: row for row in self.places}
        self._restaurant_by_id = {row.id: row for row in self.restaurants}
        self._hotel_by_id = {row.id: row for row in self.hotels}

    @property
    def live(self) -> LiveResolver | None:
        if self._suppress_live:
            return None
        return self._live

    @property
    def live_enabled(self) -> bool:
        return self.live is not None

    def set_live_apis(self, enabled: bool) -> None:
        """Turn live calls on or off for the next tool use.

        The process default stays in ``Settings``. A run can override it, then
        restore that default. Enabling builds the provider stack on first use.
        """

        if enabled and self._live is None and self._settings is not None:
            forced = self._settings.model_copy(update={"use_live_apis": True})
            self._live = _live_stack(
                forced,
                client=self._client,
                cache=self._cache,
                guard=self._guard,
                today=self._today,
            )
        self._suppress_live = not enabled

    def get_place(self, place_id: str) -> Place | None:
        return self._place_by_id.get(place_id)

    def get_restaurant(self, restaurant_id: str) -> Restaurant | None:
        return self._restaurant_by_id.get(restaurant_id)

    def get_hotel(self, hotel_id: str) -> Hotel | None:
        return self._hotel_by_id.get(hotel_id)

    def search_attractions(
        self,
        *,
        area: str | None = None,
        tag: str | None = None,
        status: str | None = None,
        category: str | None = None,
    ) -> ToolResult[list[Place]]:
        rows = self.places
        if area is not None:
            rows = [row for row in rows if row.area == area]
        if status is not None:
            rows = [row for row in rows if row.operational_status == status]
        if category is not None:
            rows = [row for row in rows if row.category == category]
        if tag is not None:
            rows = [row for row in rows if tag in row.tags]
        return _result(rows, "places")

    def search_restaurants(
        self,
        *,
        area: str | None = None,
        price_band: str | None = None,
        meal_types: list[str] | None = None,
    ) -> ToolResult[list[Restaurant]]:
        """Match area, price band, and meal types. Cuisine is unspecified on every row."""

        rows = self.restaurants
        if area is not None:
            rows = [row for row in rows if row.area == area]
        if price_band is not None:
            rows = [row for row in rows if row.price_band == price_band]
        if meal_types:
            wanted = set(meal_types)
            rows = [row for row in rows if wanted.intersection(row.meal_types)]
        live = self.live
        if live is None or not rows:
            return _result(rows, "restaurants")
        enriched, degraded, error = live.enrich_restaurants(area or "dubai", rows)
        result = _result(enriched, "restaurants")
        if any("Overpass" in row.source for row in enriched):
            result = result.model_copy(update={"source": f"{result.source}; {OSM_ODBL}"})
        if degraded:
            return result.model_copy(update={"degraded": True, "error": error})
        return result

    def search_hotels(
        self,
        *,
        area: str | None = None,
        tier: str | None = None,
    ) -> ToolResult[list[Hotel]]:
        rows = self.hotels
        if area is not None:
            rows = [row for row in rows if row.area == area]
        if tier is not None:
            rows = [row for row in rows if row.tier == tier]
        return _result(rows, "hotels")

    def get_transport_options(self) -> ToolResult[list[TransportOption]]:
        silver = [row for row in self.fares if row.mode == "metro" and row.card_type == "silver"]
        taxi = next((row for row in self.fares if row.mode == "taxi"), None)
        abra = next((row for row in self.fares if row.mode == "ferry"), None)
        options: list[TransportOption] = []
        if silver:
            summary = ", ".join(f"zone {row.zone_rule} AED {row.price_aed:g}" for row in silver)
            options.append(
                TransportOption(
                    id="metro-silver",
                    mode="metro",
                    name="Metro and tram (Silver Nol)",
                    fare_summary=summary,
                    notes="Default traveler card. Tram uses the same Silver fares.",
                    provenance=silver[0].provenance,
                    source=silver[0].source,
                    as_of=silver[0].as_of,
                )
            )
        if taxi is not None:
            options.append(
                TransportOption(
                    id="taxi",
                    mode="taxi",
                    name="Taxi",
                    fare_summary="Flag AED 5 daytime, AED 2.45/km, minimum AED 12",
                    provenance=taxi.provenance,
                    source=taxi.source,
                    as_of=taxi.as_of,
                )
            )
        if abra is not None:
            options.append(
                TransportOption(
                    id="abra",
                    mode="ferry",
                    name="Abra",
                    fare_summary=f"AED {abra.price_aed:g} creek crossing",
                    provenance=abra.provenance,
                    source=abra.source,
                    as_of=abra.as_of,
                )
            )
        return ToolResult(
            data=options,
            provenance=options[0].provenance if options else "estimated",
            source=options[0].source if options else _SOURCE,
        )

    def fare_calculator(
        self,
        *,
        mode: str,
        span: int = 1,
        km: float = 0,
        when: time | None = None,
    ) -> ToolResult[float]:
        if mode in {"metro", "tram"}:
            fare = silver_metro_fare(self.fares, span)
            return ToolResult(
                data=fare.price_aed,
                provenance=fare.provenance,
                source=fare.source,
            )
        if mode == "ferry":
            fare = abra_fare(self.fares)
            return ToolResult(
                data=fare.price_aed,
                provenance=fare.provenance,
                source=fare.source,
            )
        cost, fare = taxi_fare_aed(self.fares, km, when)
        return ToolResult(data=cost, provenance=fare.provenance, source=fare.source)

    def price_lookup(
        self,
        *,
        category: str | None = None,
        tier: str | None = None,
    ) -> ToolResult[list[PriceBand]]:
        rows = self.bands
        if category is not None:
            rows = [row for row in rows if row.category == category]
        if tier is not None:
            rows = [row for row in rows if row.tier == tier]
        return _result(rows, "price_bands")

    def route_between(
        self,
        from_id: str,
        to_id: str,
        *,
        when: time | None = None,
    ) -> ToolResult[Leg]:
        origin = self._as_stop(from_id)
        dest = self._as_stop(to_id)
        if origin is None or dest is None:
            missing = from_id if origin is None else to_id
            blank = Leg(
                from_id=from_id,
                to_id=to_id,
                mode="walk",
                minutes=0,
                distance_km=0,
                cost_aed=0,
                provenance="estimated",
                source=_SOURCE,
            )
            return ToolResult(
                data=blank,
                provenance="estimated",
                source=_SOURCE,
                degraded=True,
                error=f"Unknown stop {missing}",
            )
        offline = route_leg(origin, dest, self.graph, self.fares, when=when)
        live = self.live
        if offline.mode in {"walk", "ferry"} or live is None:
            return ToolResult(
                data=offline,
                provenance=offline.provenance,
                source=offline.source,
                degraded=False,
            )
        road_result = live.road((origin.lat, origin.lng), (dest.lat, dest.lng))
        if road_result is None:
            return ToolResult(
                data=offline,
                provenance=offline.provenance,
                source=offline.source,
                degraded=True,
                error=live.last_error,
            )
        road, fell_back = road_result
        cost, fare = taxi_fare_aed(self.fares, road.distance_km, when)
        leg = Leg(
            from_id=origin.id,
            to_id=dest.id,
            mode="taxi",
            minutes=road.minutes,
            distance_km=road.distance_km,
            cost_aed=cost,
            provenance="api",
            source=f"{road.provider}; {road.attribution}; fare {fare.source}",
            as_of=fare.as_of,
        )
        return ToolResult(
            data=leg,
            provenance="api",
            source=leg.source,
            degraded=fell_back,
            error=live.last_error if fell_back else None,
        )

    def route_matrix(self, stop_ids: list[str]) -> ToolResult[list[list[float | None]]]:
        stops = [self._as_stop(stop_id) for stop_id in stop_ids]
        if any(stop is None for stop in stops):
            return ToolResult(
                data=[],
                provenance="estimated",
                source=_SOURCE,
                degraded=True,
                error="Unknown stop in matrix",
            )
        points = [(stop.lat, stop.lng) for stop in stops if stop is not None]
        live = self.live
        if live is not None:
            grid = live.matrix(points)
            if grid is not None:
                return ToolResult(
                    data=grid,
                    provenance="api",
                    source=f"openrouteservice; {OSM_ODBL}",
                )
        grid = []
        for origin in stops:
            row: list[float | None] = []
            for dest in stops:
                if origin is None or dest is None or origin.id == dest.id:
                    row.append(0.0)
                    continue
                row.append(
                    float(route_leg(origin, dest, self.graph, self.fares).minutes)
                )
            grid.append(row)
        return ToolResult(
            data=grid,
            provenance="estimated",
            source=_SOURCE,
            degraded=live is not None,
            error=live.last_error if live is not None else None,
        )

    def get_weather(self, month: int, *, on: date | None = None) -> ToolResult[ClimateMonth]:
        row = next((item for item in self.climate if item.month == month), None)
        if row is None:
            raise ValueError(f"No climate row for month {month}")
        live = self.live
        if live is None or on is None:
            return ToolResult(data=row, provenance=row.provenance, source=row.source)
        forecast = live.forecast(on)
        if forecast is None:
            return ToolResult(
                data=row,
                provenance=row.provenance,
                source=row.source,
                degraded=True,
                error=live.last_error,
            )
        return ToolResult(data=forecast, provenance="api", source=forecast.source)

    def holiday_lookup(self, start: date, end: date) -> ToolResult[list[Holiday]]:
        rows = [
            row
            for row in self.holidays
            if row.start <= end and row.end >= start
        ]
        return _result(rows, "holidays")

    def _as_stop(self, stop_id: str) -> Place | None:
        place = self.get_place(stop_id)
        if place is not None:
            return place
        restaurant = self.get_restaurant(stop_id)
        if restaurant is None:
            hotel = self.get_hotel(stop_id)
            if hotel is None:
                return None
            return Place(
                id=hotel.id,
                name=hotel.name,
                category="hotel",
                area=hotel.area,
                lat=hotel.lat,
                lng=hotel.lng,
                indoor=True,
                operational_status="open",
                provenance=hotel.provenance,
                source=hotel.source,
                as_of=hotel.as_of,
            )
        return Place(
            id=restaurant.id,
            name=restaurant.name,
            category="restaurant",
            area=restaurant.area,
            lat=restaurant.lat,
            lng=restaurant.lng,
            opening_hours=restaurant.opening_hours,
            indoor=True,
            operational_status="open",
            provenance=restaurant.provenance,
            source=restaurant.source,
            as_of=restaurant.as_of,
        )


def _live_stack(
    settings: Settings | None,
    *,
    client: httpx.Client | None,
    cache: Cache | None,
    guard: SessionGuard | None,
    today: date | None,
) -> LiveResolver | None:
    if settings is None or not settings.use_live_apis:
        return None
    resolved_guard = guard or SessionGuard(budget_limit=settings.api_call_budget)
    if today is not None:
        pinned = today
        resolved_guard.today = lambda: pinned
    store = cache if cache is not None else open_cache(settings.cache_store_url)
    return LiveResolver(
        settings,
        store,
        resolved_guard,
        client=client,
        today=today,
    )


def _result[T](rows: list[T], table: str) -> ToolResult[list[T]]:
    provenance = "estimated"
    source = _SOURCE
    if rows and hasattr(rows[0], "provenance"):
        provenance = "verified"
        for row in rows:
            source = getattr(row, "source", source)
            if getattr(row, "provenance", "estimated") != "verified":
                provenance = "estimated"
                break
    return ToolResult(data=rows, provenance=provenance, source=source or f"{_SOURCE}:{table}")
