"""Open-Meteo daily forecast. Dates outside the horizon are not requested."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import httpx

from travel_planner.data.cache import Cache
from travel_planner.data.providers.attribution import OPEN_METEO_CC_BY, USER_AGENT
from travel_planner.data.providers.openrouteservice import _send
from travel_planner.data.resilience import ProviderHTTPError, SessionGuard, guarded_call

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DUBAI_LAT = 25.2048
DUBAI_LNG = 55.2708
HORIZON_DAYS = 16
PER_MINUTE = 60


class ForecastOutOfRange(Exception):
    pass


@dataclass(frozen=True)
class DailyForecast:
    day: date
    high_c: float
    low_c: float
    rain_mm: float
    humidity_pct: float
    source: str


class OpenMeteo:
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

    def forecast(self, day: date, *, today: date) -> DailyForecast:
        if day < today or day > today + timedelta(days=HORIZON_DAYS):
            raise ForecastOutOfRange(
                f"{day.isoformat()} is outside the Open-Meteo forecast window"
            )

        def call() -> DailyForecast:
            payload = _send(
                self.client,
                self.guard,
                "GET",
                FORECAST_URL,
                headers={"User-Agent": USER_AGENT},
                params={
                    "latitude": DUBAI_LAT,
                    "longitude": DUBAI_LNG,
                    "daily": (
                        "temperature_2m_max,temperature_2m_min,"
                        "precipitation_sum,relative_humidity_2m_mean"
                    ),
                    "timezone": "Asia/Dubai",
                    "start_date": day.isoformat(),
                    "end_date": day.isoformat(),
                },
            )
            return _parse(payload, day)

        return guarded_call(
            self.guard,
            self.cache,
            provider="open-meteo",
            per_minute=self.per_minute,
            quota="open-meteo",
            quota_limit=10000,
            fn=call,
        )


def _parse(payload: dict, day: date) -> DailyForecast:
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise ProviderHTTPError(502, "Open-Meteo response has no daily block")
    times = daily.get("time") or []
    try:
        index = list(times).index(day.isoformat())
    except ValueError as exc:
        raise ProviderHTTPError(502, "Open-Meteo did not return the requested day") from exc
    high = _at(daily, "temperature_2m_max", index)
    low = _at(daily, "temperature_2m_min", index)
    rain = _at(daily, "precipitation_sum", index)
    humidity = _at(daily, "relative_humidity_2m_mean", index)
    return DailyForecast(
        day=day,
        high_c=high,
        low_c=low,
        rain_mm=max(0.0, rain),
        humidity_pct=min(100.0, max(0.0, humidity)),
        source=f"open-meteo forecast; {OPEN_METEO_CC_BY}",
    )


def _at(daily: dict, key: str, index: int) -> float:
    values = daily.get(key) or []
    if index >= len(values) or values[index] is None:
        raise ProviderHTTPError(502, f"Open-Meteo is missing {key}")
    return float(values[index])
