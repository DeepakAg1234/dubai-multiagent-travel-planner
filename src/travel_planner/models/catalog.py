"""Curated-dataset entities and the stay/transport options built from them."""

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from travel_planner.models.common import PriceRange, Sourced

HotelTier = Literal["budget", "mid", "luxury"]
PriceTier = Literal["budget", "mid", "upscale"]
CrowdLevel = Literal["low", "medium", "high"]
OperationalStatus = Literal["open", "closed", "reopening"]
Season = Literal["peak", "summer"]
TransportMode = Literal["walk", "metro", "bus", "taxi", "tram", "ferry", "drive"]


class Place(Sourced):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    area: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    tags: list[str] = Field(default_factory=list)
    price_aed: PriceRange | None = None
    crowd_level: CrowdLevel | None = None
    typical_visit_minutes: int | None = Field(default=None, ge=0)
    opening_hours: dict[str, str] | None = None
    indoor: bool | None = None
    timed_entry: bool = False
    operational_status: OperationalStatus = "open"
    status_as_of: date | None = None
    official_url: str | None = None


class Restaurant(Sourced):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    cuisine: str = Field(min_length=1)
    area: str = Field(min_length=1)
    lat: float
    lng: float
    price_band: PriceTier
    meal_types: list[str] = Field(default_factory=list)
    opening_hours: dict[str, str] | None = None
    price_aed: PriceRange | None = None


class Hotel(Sourced):
    """One property with a peak range and a summer range."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    area: str = Field(min_length=1)
    tier: HotelTier
    lat: float
    lng: float
    stars: float | None = Field(default=None, ge=0, le=5)
    metro_nearby: str | None = None
    official_url: str | None = None
    peak_nightly_min: float = Field(ge=0)
    peak_nightly_max: float = Field(ge=0)
    summer_nightly_min: float = Field(ge=0)
    summer_nightly_max: float = Field(ge=0)

    def stay_option(self, season: Season) -> "StayOption":
        if season == "peak":
            low, high = self.peak_nightly_min, self.peak_nightly_max
        else:
            low, high = self.summer_nightly_min, self.summer_nightly_max
        return StayOption(
            provenance=self.provenance,
            source=self.source,
            as_of=self.as_of,
            id=self.id,
            name=self.name,
            area=self.area,
            tier=self.tier,
            season=season,
            nightly_min_aed=low,
            nightly_max_aed=high,
            lat=self.lat,
            lng=self.lng,
            metro_nearby=self.metro_nearby,
        )


class StayOption(Sourced):
    id: str
    name: str
    area: str
    tier: HotelTier
    season: Season
    nightly_min_aed: float = Field(ge=0)
    nightly_max_aed: float = Field(ge=0)
    lat: float
    lng: float
    metro_nearby: str | None = None


class TransportOption(Sourced):
    id: str
    mode: TransportMode
    name: str
    fare_summary: str | None = None
    notes: str | None = None


class TransitStation(Sourced):
    id: str
    name: str
    line: str
    code: str | None = None
    lat: float
    lng: float
    zone: str | None = None


class TransitEdge(Sourced):
    id: str
    from_id: str
    to_id: str
    line: str
    minutes: int = Field(ge=1)


class Fare(Sourced):
    id: str
    mode: str
    zone_rule: str
    price_aed: float = Field(ge=0)
    card_type: str
    notes: str | None = None


class PriceBand(Sourced):
    id: str
    category: str
    tier: str
    min_aed: float = Field(ge=0)
    max_aed: float = Field(ge=0)


class ClimateMonth(Sourced):
    month: int = Field(ge=1, le=12)
    avg_high_c: float
    avg_low_c: float
    rain_mm: float = Field(ge=0)
    humidity_pct: float = Field(ge=0, le=100)


HolidayKind = Literal["ramadan", "eid", "public_holiday"]
HolidayEffect = Literal[
    "drop_lunch",
    "heritage_may_close_first_day",
    "high_crowd",
]


class Holiday(Sourced):
    """A city-wide date range. Effects are category rules, not per-place closures."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: HolidayKind
    start: date
    end: date
    effects: list[HolidayEffect] = Field(default_factory=list)
    notes: str | None = None

    @model_validator(mode="after")
    def end_covers_start(self) -> "Holiday":
        if self.end < self.start:
            raise ValueError("end is before start")
        return self
