"""Live adapters, recorded responses, and the offline fallback.

Nothing in this module opens a socket. Providers see an httpx mock transport
loaded from tests/cassettes.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from travel_planner.config import Settings
from travel_planner.data.cache import NullCache, SqliteCache, open_cache
from travel_planner.data.live import LiveResolver
from travel_planner.data.local.sqlite import SqliteCatalog, build_database
from travel_planner.data.providers.attribution import OPEN_METEO_CC_BY, OSM_ODBL
from travel_planner.data.resilience import CircuitBreaker, SessionGuard, SlidingWindowLimiter
from travel_planner.service import PlannerService
from travel_planner.tools.catalog import CatalogTools

CASSETTES = Path(__file__).resolve().parents[1] / "tests" / "cassettes"
TODAY = date(2026, 11, 18)
EID = date(2026, 3, 19)


def _json(name: str) -> dict:
    return json.loads((CASSETTES / name).read_text(encoding="utf-8"))


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "use_live_apis": True,
        "ors_api_key": "test-key",
        "cache_store_url": "",
        "groq_api_key": "",
        "ollama_api_key": "",
        "anthropic_api_key": "",
        "llm_api_key": "",
        "api_call_budget": 40,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def _guard(**overrides: object) -> SessionGuard:
    guard = SessionGuard(
        budget_limit=40,
        attempts=1,
        backoff_seconds=0,
        sleep=lambda _seconds: None,
        today=lambda: TODAY,
    )
    for key, value in overrides.items():
        setattr(guard, key, value)
    return guard


@pytest.fixture(scope="module")
def catalog(tmp_path_factory, seed) -> SqliteCatalog:
    path = tmp_path_factory.mktemp("phase5") / "dubai.sqlite"
    build_database(seed, path)
    return SqliteCatalog(path)


def _tools(
    catalog: SqliteCatalog,
    handler,
    *,
    settings: Settings | None = None,
    guard: SessionGuard | None = None,
    cache=None,
    today: date | None = TODAY,
) -> CatalogTools:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return CatalogTools(
        catalog,
        settings=settings or _settings(),
        client=client,
        cache=cache,
        guard=guard or _guard(),
        today=today,
    )


def _far_pair(tools: CatalogTools):
    origin = next(row for row in tools.places if row.area == "Old Dubai")
    dest = next(row for row in tools.places if row.area == "Marina / JBR")
    return origin, dest


def test_circuit_breaker_opens_for_the_session() -> None:
    breaker = CircuitBreaker("openrouteservice", threshold=3)
    assert breaker.allow()
    breaker.failure()
    breaker.failure()
    assert breaker.allow()
    breaker.failure()
    assert breaker.allow() is False
    breaker.success()
    assert breaker.allow() is False


def test_rate_limiter_blocks_until_the_window_moves() -> None:
    now = {"t": 0.0}
    limiter = SlidingWindowLimiter(2, clock=lambda: now["t"])
    assert limiter.allow()
    assert limiter.allow()
    assert limiter.allow() is False
    now["t"] = 59.0
    assert limiter.allow() is False
    now["t"] = 60.0
    assert limiter.allow()


def test_empty_cache_url_does_not_store(tmp_path) -> None:
    cache = open_cache("")
    assert isinstance(cache, NullCache)
    cache.set("route", "1", 10)
    assert cache.get("route") is None
    with pytest.raises(ValueError, match="Unsupported CACHE_STORE_URL"):
        open_cache("redis://localhost/0")
    sqlite_cache = SqliteCache(tmp_path / "cache.sqlite")
    sqlite_cache.set("warm", "yes", 0)
    assert sqlite_cache.get("warm") is None
    sqlite_cache.set("warm", "yes", 60)
    assert sqlite_cache.get("warm") == "yes"


def test_ors_directions_cassette_sets_api_provenance(catalog: SqliteCatalog) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization", "")
        return httpx.Response(200, json=_json("ors_directions.json"))

    tools = _tools(catalog, handler)
    origin, dest = _far_pair(tools)
    hotels_before = tools.get_hotel(
        next(row.id for row in tools.hotels if row.area == "Old Dubai" and row.tier == "budget")
    )
    assert hotels_before is not None
    nightly = hotels_before.peak_nightly_min
    leg = tools.route_between(origin.id, dest.id)
    assert seen["auth"] == "test-key"
    assert leg.provenance == "api"
    assert leg.degraded is False
    assert leg.data.minutes == 9
    assert leg.data.mode == "taxi"
    assert OSM_ODBL in leg.source
    assert tools.get_hotel(hotels_before.id).peak_nightly_min == nightly  # type: ignore[union-attr]


def test_ors_failure_falls_through_to_osrm_then_the_graph(catalog: SqliteCatalog) -> None:
    def osrm_handler(request: httpx.Request) -> httpx.Response:
        if "openrouteservice.org" in str(request.url):
            return httpx.Response(500, json={"error": "down"})
        return httpx.Response(200, json=_json("osrm_route.json"))

    tools = _tools(catalog, osrm_handler)
    origin, dest = _far_pair(tools)
    leg = tools.route_between(origin.id, dest.id)
    assert leg.provenance == "api"
    assert leg.degraded is True
    assert leg.data.minutes == 10
    assert "osrm" in leg.source

    def down(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down")

    offline = _tools(catalog, down).route_between(origin.id, dest.id)
    assert offline.degraded is True
    assert offline.provenance == "estimated"
    assert offline.data.mode in {"metro", "tram", "taxi", "walk"}
    assert "openrouteservice" not in offline.source


def test_repeated_failures_open_the_breaker(catalog: SqliteCatalog) -> None:
    calls = {"ors": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "openrouteservice.org" in str(request.url):
            calls["ors"] += 1
            return httpx.Response(500, json={"error": "down"})
        return httpx.Response(500, text="down")

    tools = _tools(catalog, handler, guard=_guard(failure_threshold=3))
    origin, dest = _far_pair(tools)
    for _ in range(4):
        result = tools.route_between(origin.id, dest.id)
        assert result.degraded is True
    assert calls["ors"] == 3


def test_per_minute_limit_skips_the_provider(catalog: SqliteCatalog) -> None:
    calls = {"ors": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "openrouteservice.org" in str(request.url):
            calls["ors"] += 1
            return httpx.Response(200, json=_json("ors_directions.json"))
        return httpx.Response(200, json=_json("osrm_route.json"))

    guard = _guard()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    resolver = LiveResolver(
        _settings(),
        NullCache(),
        guard,
        client=client,
        today=TODAY,
    )
    resolver.ors.per_minute = 1
    origin = (25.26, 55.30)
    dest = (25.08, 55.14)
    first = resolver.road(origin, dest)
    second = resolver.road((25.27, 55.31), (25.09, 55.15))
    assert first is not None and first[1] is False
    assert second is not None and second[0].provider == "osrm" and second[1] is True
    assert calls["ors"] == 1


def test_call_budget_stops_live_routing(catalog: SqliteCatalog) -> None:
    calls = {"http": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["http"] += 1
        if "openrouteservice.org" in str(request.url):
            return httpx.Response(200, json=_json("ors_directions.json"))
        return httpx.Response(200, json=_json("osrm_route.json"))

    tools = _tools(catalog, handler, guard=_guard(budget_limit=1))
    origin, dest = _far_pair(tools)
    first = tools.route_between(origin.id, dest.id)
    second = tools.route_between(dest.id, origin.id)
    assert first.provenance == "api"
    assert second.degraded is True
    assert second.provenance == "estimated"
    assert calls["http"] == 1


def test_directions_daily_quota_persists_in_the_cache(tmp_path) -> None:
    calls = {"ors": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "openrouteservice.org" in str(request.url):
            calls["ors"] += 1
            return httpx.Response(200, json=_json("ors_directions.json"))
        return httpx.Response(200, json=_json("osrm_route.json"))

    cache = SqliteCache(tmp_path / "quota.sqlite")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    first = LiveResolver(_settings(), cache, _guard(), client=client, today=TODAY)
    first.ors.directions_daily = 1
    first_road = first.road((25.26, 55.30), (25.08, 55.14))
    assert first_road is not None and first_road[0].provider == "openrouteservice"
    second = LiveResolver(_settings(), cache, _guard(), client=client, today=TODAY)
    second.ors.directions_daily = 1
    second_road = second.road((25.27, 55.31), (25.09, 55.15))
    assert second_road is not None
    assert second_road[0].provider == "osrm"
    assert second_road[1] is True
    assert calls["ors"] == 1


def test_matrix_cassette_and_offline_grid(catalog: SqliteCatalog) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/matrix/" in str(request.url)
        return httpx.Response(200, json=_json("ors_matrix.json"))

    tools = _tools(catalog, handler)
    origin, dest = _far_pair(tools)
    matrix = tools.route_matrix([origin.id, dest.id])
    assert matrix.provenance == "api"
    assert matrix.degraded is False
    assert matrix.data[0][1] == 9.0
    assert OSM_ODBL in matrix.source

    offline = CatalogTools(catalog).route_matrix([origin.id, dest.id])
    assert offline.provenance == "estimated"
    assert offline.degraded is False
    assert offline.data[0][0] == 0


def test_overpass_keeps_prices_and_fills_cuisine(catalog: SqliteCatalog) -> None:
    bodies: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(parse_qs(request.content.decode())["data"][0])
        return httpx.Response(200, json=_json("overpass_restaurants.json"))

    tools = _tools(catalog, handler)
    hotel = next(row for row in tools.hotels if row.tier == "budget")
    nightly = (hotel.peak_nightly_min, hotel.summer_nightly_min)
    found = tools.search_restaurants(area="Old Dubai", price_band="budget", meal_types=["lunch"])
    assert "[timeout:25]" in bodies[0]
    assert "[maxsize:1048576]" in bodies[0]
    matched = next(row for row in found.data if row.name == "Pak Liyari Restaurant")
    assert matched.cuisine == "pakistani"
    assert matched.opening_hours == {"daily": "12:00-23:00"}
    assert matched.price_band == "budget"
    assert matched.price_aed is None
    assert matched.provenance == "estimated"
    assert OSM_ODBL in matched.source
    assert OSM_ODBL in found.source
    stored = tools.get_restaurant(matched.id)
    assert stored is not None and stored.cuisine == "unspecified"
    untouched = tools.get_hotel(hotel.id)
    assert untouched is not None
    assert (untouched.peak_nightly_min, untouched.summer_nightly_min) == nightly
    place = tools.search_attractions(area="Old Dubai", status="open").data[0]
    assert place.operational_status == "open"


def test_overpass_429_and_504_keep_the_curated_row(catalog: SqliteCatalog) -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        status = 429 if calls["n"] == 1 else 504
        return httpx.Response(status, text="slow down")

    tools = _tools(catalog, handler, guard=_guard(attempts=3))
    found = tools.search_restaurants(area="Old Dubai", price_band="budget")
    assert found.degraded is True
    assert calls["n"] == 1
    assert all(row.cuisine == "unspecified" for row in found.data)
    assert all(row.price_band == "budget" for row in found.data)
    again = tools.search_restaurants(area="Downtown", price_band="mid")
    assert again.degraded is True
    assert calls["n"] == 2


def test_forecast_cassette_and_climate_fallback(catalog: SqliteCatalog) -> None:
    calls = {"meteo": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["meteo"] += 1
        payload = _json("open_meteo_forecast.json")
        payload["daily"]["time"] = [request.url.params["start_date"]]
        return httpx.Response(200, json=payload)

    from travel_planner.data.cache import MemoryCache

    tools = _tools(catalog, handler, cache=MemoryCache(), today=TODAY)
    forecast = tools.get_weather(11, on=date(2026, 11, 20))
    assert forecast.provenance == "api"
    assert forecast.degraded is False
    assert forecast.data.avg_high_c == 32.4
    assert OPEN_METEO_CC_BY in forecast.source
    cached = tools.get_weather(11, on=date(2026, 11, 20))
    assert cached.data.avg_high_c == 32.4
    assert calls["meteo"] == 1

    beyond = tools.get_weather(3, on=EID)
    assert beyond.degraded is True
    assert beyond.provenance == "estimated"
    assert beyond.data.avg_high_c == 28.4
    assert calls["meteo"] == 1

    month_only = tools.get_weather(7)
    assert month_only.degraded is False
    assert month_only.data.avg_high_c == 41
    assert calls["meteo"] == 1


def test_attractions_and_hotels_do_not_call_live_apis(catalog: SqliteCatalog) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("search_attractions and search_hotels stay on the catalog")

    tools = _tools(catalog, handler)
    assert tools.search_attractions(area="Downtown", status="open").data
    assert tools.search_hotels(area="Downtown", tier="luxury").data
    assert tools.live_enabled is True


def test_retry_then_success_does_not_open_the_breaker(catalog: SqliteCatalog) -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="retry")
        return httpx.Response(200, json=_json("ors_directions.json"))

    tools = _tools(catalog, handler, guard=_guard(attempts=3))
    origin, dest = _far_pair(tools)
    leg = tools.route_between(origin.id, dest.id)
    assert leg.provenance == "api"
    assert calls["n"] == 2
    assert tools._live is not None
    assert tools._live.guard.breaker("openrouteservice").opened is False


def _offline_settings() -> Settings:
    return _settings(
        use_live_apis=False,
        ors_api_key="",
        cache_store_url="",
    )


@pytest.mark.offline
def test_offline_flow_keeps_holiday_effects_and_the_transit_graph() -> None:
    service = PlannerService(_offline_settings())
    request = (
        "2 days in Dubai, culture and food, AED 5000, affordable hotel, start:2026-03-19"
    )
    list(service.run(request, thread_id="offline-eid"))
    values = service.values("offline-eid")
    final = values["final_itinerary"]
    assert final is not None
    assert final.days[0].holiday_note
    notes = [slot.notes or "" for slot in final.days[0].slots]
    assert not any(note == "lunch" for note in notes)
    legs = [leg for day in final.days for leg in day.legs]
    assert legs
    assert all(leg.provenance != "api" for leg in legs)
    assert all("openrouteservice" not in leg.source for leg in legs)
    scheduled = {slot.place_id for day in final.days for slot in day.slots}
    assert "place-museum-of-the-future" not in scheduled
    assert "place-dubai-museum" not in scheduled


def test_the_same_request_completes_with_apis_on_and_off() -> None:
    request = "2 days in Dubai, culture and food, AED 5000, affordable hotel, start:2026-11-20"

    def handler(request_http: httpx.Request) -> httpx.Response:
        url = str(request_http.url)
        if "openrouteservice.org" in url and "/matrix/" in url:
            return httpx.Response(200, json=_json("ors_matrix.json"))
        if "openrouteservice.org" in url:
            return httpx.Response(200, json=_json("ors_directions.json"))
        if "project-osrm.org" in url:
            return httpx.Response(200, json=_json("osrm_route.json"))
        if "overpass-api.de" in url:
            return httpx.Response(200, json={"elements": []})
        if "open-meteo.com" in url:
            payload = _json("open_meteo_forecast.json")
            payload["daily"]["time"] = [request_http.url.params["start_date"]]
            return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"error": url})

    live = PlannerService(
        _settings(),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        today=TODAY,
    )
    offline = PlannerService(_offline_settings(), today=TODAY)
    list(live.run(request, thread_id="live-on"))
    list(offline.run(request, thread_id="live-off"))
    live_final = live.values("live-on")["final_itinerary"]
    offline_final = offline.values("live-off")["final_itinerary"]
    assert live_final is not None and offline_final is not None
    assert live_final.days and offline_final.days
    warnings = list(live.values("live-on")["warnings"])
    assert any(OPEN_METEO_CC_BY in note for note in warnings)

    eid = "2 days in Dubai, culture and food, AED 5000, affordable hotel, start:2026-03-19"
    list(live.run(eid, thread_id="live-eid"))
    eid_values = live.values("live-eid")
    eid_final = eid_values["final_itinerary"]
    assert eid_final is not None
    assert eid_final.days[0].holiday_note
    assert any("monthly climate" in note for note in eid_values["warnings"])
    meal_notes = [slot.notes or "" for slot in eid_final.days[0].slots]
    assert not any(note == "lunch" for note in meal_notes)
