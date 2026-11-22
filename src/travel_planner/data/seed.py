"""Load and check the JSON seed files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from travel_planner.config import REPO_ROOT
from travel_planner.data.areas import PLANNING_AREAS
from travel_planner.models import (
    ClimateMonth,
    Fare,
    Holiday,
    Hotel,
    Place,
    PriceBand,
    Restaurant,
    TransitEdge,
    TransitStation,
)

SEED_DIR = REPO_ROOT / "data" / "seed"

# Interest floors from the implementation plan. The low end is required.
# The high end is the curation target, not a cap: real free beaches and malls
# push some buckets past the top of the published range.
PLACE_FLOORS: dict[str, int] = {
    "culture": 15,
    "landmark": 10,
    "outdoor": 10,
    "mall": 8,
    "family": 8,
    "nightlife": 6,
    "free_or_cheap": 15,
}


class SeedError(ValueError):
    """Seed JSON failed validation or the coverage floors."""


@dataclass(frozen=True)
class SeedBundle:
    places: list[Place]
    restaurants: list[Restaurant]
    hotels: list[Hotel]
    stations: list[TransitStation]
    edges: list[TransitEdge]
    fares: list[Fare]
    price_bands: list[PriceBand]
    climate: list[ClimateMonth]
    holidays: list[Holiday]


def _read_list(path: Path) -> list[object]:
    if not path.is_file():
        raise SeedError(f"missing seed file: {path.name}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SeedError(f"{path.name} must be a JSON list")
    return payload


def _parse[T](path: Path, adapter: TypeAdapter[list[T]]) -> list[T]:
    try:
        return adapter.validate_python(_read_list(path))
    except ValidationError as exc:
        raise SeedError(f"{path.name} failed validation: {exc}") from exc


def load_seed(directory: Path | None = None) -> SeedBundle:
    folder = directory or SEED_DIR
    bundle = SeedBundle(
        places=_parse(folder / "places.json", TypeAdapter(list[Place])),
        restaurants=_parse(folder / "restaurants.json", TypeAdapter(list[Restaurant])),
        hotels=_parse(folder / "hotels.json", TypeAdapter(list[Hotel])),
        stations=_parse(folder / "transit_stations.json", TypeAdapter(list[TransitStation])),
        edges=_parse(folder / "transit_edges.json", TypeAdapter(list[TransitEdge])),
        fares=_parse(folder / "fares.json", TypeAdapter(list[Fare])),
        price_bands=_parse(folder / "price_bands.json", TypeAdapter(list[PriceBand])),
        climate=_parse(folder / "climate.json", TypeAdapter(list[ClimateMonth])),
        holidays=_parse(folder / "holidays.json", TypeAdapter(list[Holiday])),
    )
    _require_facts(bundle)
    _require_coverage(bundle)
    return bundle


def _require_sourced(kind: str, row_id: str, source: str, as_of: object) -> None:
    if not source.strip():
        raise SeedError(f"{kind} {row_id} is missing source")
    if as_of is None:
        raise SeedError(f"{kind} {row_id} is missing as_of")


def _require_facts(bundle: SeedBundle) -> None:
    seen: set[str] = set()
    for place in bundle.places:
        if place.id in seen:
            raise SeedError(f"duplicate place id {place.id}")
        seen.add(place.id)
        _require_sourced("place", place.id, place.source, place.as_of)
        if place.price_aed is None:
            raise SeedError(f"place {place.id} is missing a price")
    seen.clear()
    for restaurant in bundle.restaurants:
        if restaurant.id in seen:
            raise SeedError(f"duplicate restaurant id {restaurant.id}")
        seen.add(restaurant.id)
        _require_sourced("restaurant", restaurant.id, restaurant.source, restaurant.as_of)
    seen.clear()
    for hotel in bundle.hotels:
        if hotel.id in seen:
            raise SeedError(f"duplicate hotel id {hotel.id}")
        seen.add(hotel.id)
        _require_sourced("hotel", hotel.id, hotel.source, hotel.as_of)
        if hotel.peak_nightly_max < hotel.peak_nightly_min:
            raise SeedError(f"hotel {hotel.id} has an inverted peak range")
        if hotel.summer_nightly_max < hotel.summer_nightly_min:
            raise SeedError(f"hotel {hotel.id} has an inverted summer range")
    station_ids = {station.id for station in bundle.stations}
    if len(station_ids) != len(bundle.stations):
        raise SeedError("duplicate transit station id")
    for station in bundle.stations:
        _require_sourced("station", station.id, station.source, station.as_of)
    edge_ids: set[str] = set()
    for edge in bundle.edges:
        if edge.id in edge_ids:
            raise SeedError(f"duplicate edge id {edge.id}")
        edge_ids.add(edge.id)
        _require_sourced("edge", edge.id, edge.source, edge.as_of)
        if edge.from_id not in station_ids or edge.to_id not in station_ids:
            raise SeedError(f"edge {edge.id} references an unknown station")
    for fare in bundle.fares:
        _require_sourced("fare", fare.id, fare.source, fare.as_of)
    for band in bundle.price_bands:
        _require_sourced("price band", band.id, band.source, band.as_of)
        if band.max_aed < band.min_aed:
            raise SeedError(f"price band {band.id} is inverted")
    months = [row.month for row in bundle.climate]
    if sorted(months) != list(range(1, 13)):
        raise SeedError("climate.json must contain months 1 through 12 once each")
    for row in bundle.climate:
        _require_sourced("climate", str(row.month), row.source, row.as_of)
    _require_holidays(bundle.holidays)


def _require_holidays(rows: list[Holiday]) -> None:
    if not 10 <= len(rows) <= 24:
        raise SeedError(f"expected 10-24 holidays, found {len(rows)}")
    seen: set[str] = set()
    for row in rows:
        if row.id in seen:
            raise SeedError(f"duplicate holiday id {row.id}")
        seen.add(row.id)
        _require_sourced("holiday", row.id, row.source, row.as_of)
        span = (row.end - row.start).days + 1
        if row.kind == "ramadan" and span > 31:
            raise SeedError(f"holiday {row.id} is longer than a month")
        if row.kind == "eid" and span > 6:
            raise SeedError(f"holiday {row.id} is longer than an Eid window")
        if row.kind == "public_holiday" and span > 4:
            raise SeedError(f"holiday {row.id} is longer than a public holiday")
        if row.kind == "ramadan" and "drop_lunch" not in row.effects:
            raise SeedError(f"holiday {row.id} must drop lunch")
        if row.kind == "eid" and not {
            "heritage_may_close_first_day",
            "high_crowd",
        } <= set(row.effects):
            raise SeedError(f"holiday {row.id} is missing an Eid effect")
        if "National Day" in row.name and "high_crowd" not in row.effects:
            raise SeedError(f"holiday {row.id} must mark National Day as crowded")
    for kind in ("ramadan", "eid", "public_holiday"):
        ordered = sorted((row for row in rows if row.kind == kind), key=lambda row: row.start)
        for left, right in zip(ordered, ordered[1:], strict=False):
            if right.start <= left.end:
                raise SeedError(f"overlapping {kind} holidays {left.id} and {right.id}")
    if not any(row.kind == "ramadan" for row in rows):
        raise SeedError("holiday calendar is missing Ramadan")
    if not any(row.kind == "eid" for row in rows):
        raise SeedError("holiday calendar is missing Eid")
    if not any("National Day" in row.name for row in rows):
        raise SeedError("holiday calendar is missing National Day")


def _require_coverage(bundle: SeedBundle) -> None:
    places = bundle.places
    if not 80 <= len(places) <= 120:
        raise SeedError(f"expected 80-120 places, found {len(places)}")
    if sum("culture" in place.tags for place in places) < PLACE_FLOORS["culture"]:
        raise SeedError("culture floor not met")
    if sum("landmark" in place.tags for place in places) < PLACE_FLOORS["landmark"]:
        raise SeedError("landmark floor not met")
    outdoor = sum("beach" in place.tags or "outdoor" in place.tags for place in places)
    if outdoor < PLACE_FLOORS["outdoor"]:
        raise SeedError("beach and outdoor floor not met")
    if sum(place.category == "mall" for place in places) < PLACE_FLOORS["mall"]:
        raise SeedError("mall floor not met")
    if sum("family" in place.tags for place in places) < PLACE_FLOORS["family"]:
        raise SeedError("family floor not met")
    if sum("nightlife" in place.tags for place in places) < PLACE_FLOORS["nightlife"]:
        raise SeedError("nightlife floor not met")
    cheap = sum(
        place.price_aed is not None and place.price_aed.max_aed <= 20 for place in places
    )
    if cheap < PLACE_FLOORS["free_or_cheap"]:
        raise SeedError("free or very cheap floor not met")
    closed = [
        place
        for place in places
        if place.operational_status in {"closed", "reopening"}
    ]
    if not any("future" in place.id for place in closed):
        raise SeedError("Museum of the Future must be closed or reopening")

    if not 80 <= len(bundle.restaurants) <= 120:
        raise SeedError(f"expected 80-120 restaurants, found {len(bundle.restaurants)}")
    if not 30 <= len(bundle.hotels) <= 40:
        raise SeedError(f"expected 30-40 hotels, found {len(bundle.hotels)}")

    for area in PLANNING_AREAS:
        area_places = [place for place in places if place.area == area]
        if not area_places:
            raise SeedError(f"{area} has no places")
        meals = [row for row in bundle.restaurants if row.area == area]
        if len(meals) < 6:
            raise SeedError(f"{area} has fewer than 6 restaurants")
        tiers = {row.price_band for row in meals}
        if not {"budget", "mid", "upscale"} <= tiers:
            raise SeedError(f"{area} is missing a restaurant price band")
        hotel_tiers = {row.tier for row in bundle.hotels if row.area == area}
        if not {"budget", "mid", "luxury"} <= hotel_tiers:
            raise SeedError(f"{area} is missing a hotel tier")

    silver = {
        (fare.zone_rule, fare.price_aed)
        for fare in bundle.fares
        if fare.mode == "metro" and fare.card_type == "silver" and fare.provenance == "verified"
    }
    if ("1", 3.0) not in silver or ("2", 5.0) not in silver or ("3+", 7.5) not in silver:
        raise SeedError("verified Silver Nol metro fares are incomplete")
