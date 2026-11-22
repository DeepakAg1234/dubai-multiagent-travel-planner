"""SQLite implementations of the repository protocols."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from travel_planner.data.seed import SeedBundle
from travel_planner.models import (
    ClimateMonth,
    Fare,
    Holiday,
    Hotel,
    Place,
    PriceBand,
    PriceRange,
    Restaurant,
    TransitEdge,
    TransitStation,
)

SCHEMA = """
CREATE TABLE places (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    area TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    tags TEXT NOT NULL,
    crowd_level TEXT,
    visit_minutes INTEGER,
    indoor INTEGER,
    hours TEXT,
    price_min REAL NOT NULL,
    price_max REAL NOT NULL,
    timed_entry INTEGER NOT NULL,
    operational_status TEXT NOT NULL,
    status_as_of TEXT,
    official_url TEXT,
    provenance TEXT NOT NULL,
    source TEXT NOT NULL,
    as_of TEXT NOT NULL
);
CREATE TABLE restaurants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    cuisine TEXT NOT NULL,
    area TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    price_band TEXT NOT NULL,
    meal_types TEXT NOT NULL,
    hours TEXT,
    price_min REAL,
    price_max REAL,
    provenance TEXT NOT NULL,
    source TEXT NOT NULL,
    as_of TEXT NOT NULL
);
CREATE TABLE hotels (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    area TEXT NOT NULL,
    tier TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    stars REAL,
    metro_nearby TEXT,
    official_url TEXT,
    peak_nightly_min REAL NOT NULL,
    peak_nightly_max REAL NOT NULL,
    summer_nightly_min REAL NOT NULL,
    summer_nightly_max REAL NOT NULL,
    provenance TEXT NOT NULL,
    source TEXT NOT NULL,
    as_of TEXT NOT NULL
);
CREATE TABLE transit_stations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    line TEXT NOT NULL,
    code TEXT,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    zone TEXT,
    provenance TEXT NOT NULL,
    source TEXT NOT NULL,
    as_of TEXT NOT NULL
);
CREATE TABLE transit_edges (
    id TEXT PRIMARY KEY,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    line TEXT NOT NULL,
    minutes INTEGER NOT NULL,
    provenance TEXT NOT NULL,
    source TEXT NOT NULL,
    as_of TEXT NOT NULL
);
CREATE TABLE fares (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    zone_rule TEXT NOT NULL,
    price_aed REAL NOT NULL,
    card_type TEXT NOT NULL,
    notes TEXT,
    provenance TEXT NOT NULL,
    source TEXT NOT NULL,
    as_of TEXT NOT NULL
);
CREATE TABLE price_bands (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    tier TEXT NOT NULL,
    min_aed REAL NOT NULL,
    max_aed REAL NOT NULL,
    provenance TEXT NOT NULL,
    source TEXT NOT NULL,
    as_of TEXT NOT NULL
);
CREATE TABLE climate (
    month INTEGER PRIMARY KEY,
    avg_high_c REAL NOT NULL,
    avg_low_c REAL NOT NULL,
    rain_mm REAL NOT NULL,
    humidity_pct REAL NOT NULL,
    provenance TEXT NOT NULL,
    source TEXT NOT NULL,
    as_of TEXT NOT NULL
);
CREATE TABLE holidays (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    effects TEXT NOT NULL,
    notes TEXT,
    provenance TEXT NOT NULL,
    source TEXT NOT NULL,
    as_of TEXT NOT NULL
);
CREATE INDEX idx_places_area ON places(area);
CREATE INDEX idx_places_status ON places(operational_status);
CREATE INDEX idx_restaurants_area ON restaurants(area);
CREATE INDEX idx_hotels_area_tier ON hotels(area, tier);
"""


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _bool(value: int | None) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _price(low: float | None, high: float | None) -> PriceRange | None:
    if low is None or high is None:
        return None
    return PriceRange(min_aed=low, max_aed=high)


class SqliteCatalog:
    """All local repositories share one connection."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self._conn.close()

    def get_place(self, place_id: str) -> Place | None:
        row = self._conn.execute("SELECT * FROM places WHERE id = ?", (place_id,)).fetchone()
        return _place(row) if row else None

    def search_places(
        self,
        *,
        area: str | None = None,
        tag: str | None = None,
        status: str | None = None,
        category: str | None = None,
    ) -> list[Place]:
        clauses: list[str] = []
        params: list[object] = []
        if area is not None:
            clauses.append("area = ?")
            params.append(area)
        if status is not None:
            clauses.append("operational_status = ?")
            params.append(status)
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if tag is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM json_each(places.tags) WHERE json_each.value = ?)"
            )
            params.append(tag)
        sql = "SELECT * FROM places"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY name"
        return [_place(row) for row in self._conn.execute(sql, params)]

    def search_restaurants(
        self,
        *,
        area: str | None = None,
        tier: str | None = None,
        cuisine: str | None = None,
    ) -> list[Restaurant]:
        clauses: list[str] = []
        params: list[object] = []
        if area is not None:
            clauses.append("area = ?")
            params.append(area)
        if tier is not None:
            clauses.append("price_band = ?")
            params.append(tier)
        if cuisine is not None:
            clauses.append("cuisine = ?")
            params.append(cuisine)
        sql = "SELECT * FROM restaurants"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY name"
        return [_restaurant(row) for row in self._conn.execute(sql, params)]

    def get_hotel(self, hotel_id: str) -> Hotel | None:
        row = self._conn.execute("SELECT * FROM hotels WHERE id = ?", (hotel_id,)).fetchone()
        return _hotel(row) if row else None

    def search_hotels(
        self,
        *,
        area: str | None = None,
        tier: str | None = None,
    ) -> list[Hotel]:
        clauses: list[str] = []
        params: list[object] = []
        if area is not None:
            clauses.append("area = ?")
            params.append(area)
        if tier is not None:
            clauses.append("tier = ?")
            params.append(tier)
        sql = "SELECT * FROM hotels"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY name"
        return [_hotel(row) for row in self._conn.execute(sql, params)]

    def stations(self, *, line: str | None = None) -> list[TransitStation]:
        if line is None:
            rows = self._conn.execute("SELECT * FROM transit_stations ORDER BY name")
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM transit_stations
                WHERE line = ? OR (',' || line || ',') LIKE ?
                ORDER BY name
                """,
                (line, f"%,{line},%"),
            )
        return [_station(row) for row in rows]

    def edges(self, *, line: str | None = None) -> list[TransitEdge]:
        if line is None:
            rows = self._conn.execute("SELECT * FROM transit_edges ORDER BY line, id")
        else:
            rows = self._conn.execute(
                "SELECT * FROM transit_edges WHERE line = ? ORDER BY id",
                (line,),
            )
        return [_edge(row) for row in rows]

    def fares(self) -> list[Fare]:
        return [_fare(row) for row in self._conn.execute("SELECT * FROM fares ORDER BY id")]

    def fares_for_mode(self, mode: str) -> list[Fare]:
        rows = self._conn.execute("SELECT * FROM fares WHERE mode = ? ORDER BY id", (mode,))
        return [_fare(row) for row in rows]

    def price_bands(
        self,
        *,
        category: str | None = None,
        tier: str | None = None,
    ) -> list[PriceBand]:
        clauses: list[str] = []
        params: list[object] = []
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        if tier is not None:
            clauses.append("tier = ?")
            params.append(tier)
        sql = "SELECT * FROM price_bands"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id"
        return [_band(row) for row in self._conn.execute(sql, params)]

    def climate_month(self, month: int) -> ClimateMonth | None:
        row = self._conn.execute("SELECT * FROM climate WHERE month = ?", (month,)).fetchone()
        return _climate(row) if row else None

    def climate_all(self) -> list[ClimateMonth]:
        return [_climate(row) for row in self._conn.execute("SELECT * FROM climate ORDER BY month")]

    def holidays(self) -> list[Holiday]:
        rows = self._conn.execute("SELECT * FROM holidays ORDER BY start, id")
        return [_holiday(row) for row in rows]

    def holidays_overlapping(self, start: date, end: date) -> list[Holiday]:
        rows = self._conn.execute(
            """
            SELECT * FROM holidays
            WHERE start <= ? AND end >= ?
            ORDER BY start, id
            """,
            (end.isoformat(), start.isoformat()),
        )
        return [_holiday(row) for row in rows]


def build_database(bundle: SeedBundle, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            """
            INSERT INTO places VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    place.id,
                    place.name,
                    place.category,
                    place.area,
                    place.lat,
                    place.lng,
                    json.dumps(place.tags),
                    place.crowd_level,
                    place.typical_visit_minutes,
                    None if place.indoor is None else int(place.indoor),
                    json.dumps(place.opening_hours) if place.opening_hours else None,
                    place.price_aed.min_aed if place.price_aed else None,
                    place.price_aed.max_aed if place.price_aed else None,
                    int(place.timed_entry),
                    place.operational_status,
                    _iso(place.status_as_of),
                    place.official_url,
                    place.provenance,
                    place.source,
                    _iso(place.as_of),
                )
                for place in bundle.places
            ],
        )
        conn.executemany(
            """
            INSERT INTO restaurants VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.id,
                    row.name,
                    row.cuisine,
                    row.area,
                    row.lat,
                    row.lng,
                    row.price_band,
                    json.dumps(row.meal_types),
                    json.dumps(row.opening_hours) if row.opening_hours else None,
                    row.price_aed.min_aed if row.price_aed else None,
                    row.price_aed.max_aed if row.price_aed else None,
                    row.provenance,
                    row.source,
                    _iso(row.as_of),
                )
                for row in bundle.restaurants
            ],
        )
        conn.executemany(
            """
            INSERT INTO hotels VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                (
                    row.id,
                    row.name,
                    row.area,
                    row.tier,
                    row.lat,
                    row.lng,
                    row.stars,
                    row.metro_nearby,
                    row.official_url,
                    row.peak_nightly_min,
                    row.peak_nightly_max,
                    row.summer_nightly_min,
                    row.summer_nightly_max,
                    row.provenance,
                    row.source,
                    _iso(row.as_of),
                )
                for row in bundle.hotels
            ],
        )
        conn.executemany(
            "INSERT INTO transit_stations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row.id,
                    row.name,
                    row.line,
                    row.code,
                    row.lat,
                    row.lng,
                    row.zone,
                    row.provenance,
                    row.source,
                    _iso(row.as_of),
                )
                for row in bundle.stations
            ],
        )
        conn.executemany(
            "INSERT INTO transit_edges VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row.id,
                    row.from_id,
                    row.to_id,
                    row.line,
                    row.minutes,
                    row.provenance,
                    row.source,
                    _iso(row.as_of),
                )
                for row in bundle.edges
            ],
        )
        conn.executemany(
            "INSERT INTO fares VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row.id,
                    row.mode,
                    row.zone_rule,
                    row.price_aed,
                    row.card_type,
                    row.notes,
                    row.provenance,
                    row.source,
                    _iso(row.as_of),
                )
                for row in bundle.fares
            ],
        )
        conn.executemany(
            "INSERT INTO price_bands VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row.id,
                    row.category,
                    row.tier,
                    row.min_aed,
                    row.max_aed,
                    row.provenance,
                    row.source,
                    _iso(row.as_of),
                )
                for row in bundle.price_bands
            ],
        )
        conn.executemany(
            "INSERT INTO climate VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row.month,
                    row.avg_high_c,
                    row.avg_low_c,
                    row.rain_mm,
                    row.humidity_pct,
                    row.provenance,
                    row.source,
                    _iso(row.as_of),
                )
                for row in bundle.climate
            ],
        )
        conn.executemany(
            "INSERT INTO holidays VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row.id,
                    row.name,
                    row.kind,
                    row.start.isoformat(),
                    row.end.isoformat(),
                    json.dumps(row.effects),
                    row.notes,
                    row.provenance,
                    row.source,
                    _iso(row.as_of),
                )
                for row in bundle.holidays
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _place(row: sqlite3.Row) -> Place:
    return Place(
        id=row["id"],
        name=row["name"],
        category=row["category"],
        area=row["area"],
        lat=row["lat"],
        lng=row["lng"],
        tags=json.loads(row["tags"]),
        crowd_level=row["crowd_level"],
        typical_visit_minutes=row["visit_minutes"],
        indoor=_bool(row["indoor"]),
        opening_hours=json.loads(row["hours"]) if row["hours"] else None,
        price_aed=_price(row["price_min"], row["price_max"]),
        timed_entry=bool(row["timed_entry"]),
        operational_status=row["operational_status"],
        status_as_of=_date(row["status_as_of"]),
        official_url=row["official_url"],
        provenance=row["provenance"],
        source=row["source"],
        as_of=_date(row["as_of"]),
    )


def _restaurant(row: sqlite3.Row) -> Restaurant:
    return Restaurant(
        id=row["id"],
        name=row["name"],
        cuisine=row["cuisine"],
        area=row["area"],
        lat=row["lat"],
        lng=row["lng"],
        price_band=row["price_band"],
        meal_types=json.loads(row["meal_types"]),
        opening_hours=json.loads(row["hours"]) if row["hours"] else None,
        price_aed=_price(row["price_min"], row["price_max"]),
        provenance=row["provenance"],
        source=row["source"],
        as_of=_date(row["as_of"]),
    )


def _hotel(row: sqlite3.Row) -> Hotel:
    return Hotel(
        id=row["id"],
        name=row["name"],
        area=row["area"],
        tier=row["tier"],
        lat=row["lat"],
        lng=row["lng"],
        stars=row["stars"],
        metro_nearby=row["metro_nearby"],
        official_url=row["official_url"],
        peak_nightly_min=row["peak_nightly_min"],
        peak_nightly_max=row["peak_nightly_max"],
        summer_nightly_min=row["summer_nightly_min"],
        summer_nightly_max=row["summer_nightly_max"],
        provenance=row["provenance"],
        source=row["source"],
        as_of=_date(row["as_of"]),
    )


def _station(row: sqlite3.Row) -> TransitStation:
    return TransitStation(
        id=row["id"],
        name=row["name"],
        line=row["line"],
        code=row["code"],
        lat=row["lat"],
        lng=row["lng"],
        zone=row["zone"],
        provenance=row["provenance"],
        source=row["source"],
        as_of=_date(row["as_of"]),
    )


def _edge(row: sqlite3.Row) -> TransitEdge:
    return TransitEdge(
        id=row["id"],
        from_id=row["from_id"],
        to_id=row["to_id"],
        line=row["line"],
        minutes=row["minutes"],
        provenance=row["provenance"],
        source=row["source"],
        as_of=_date(row["as_of"]),
    )


def _fare(row: sqlite3.Row) -> Fare:
    return Fare(
        id=row["id"],
        mode=row["mode"],
        zone_rule=row["zone_rule"],
        price_aed=row["price_aed"],
        card_type=row["card_type"],
        notes=row["notes"],
        provenance=row["provenance"],
        source=row["source"],
        as_of=_date(row["as_of"]),
    )


def _band(row: sqlite3.Row) -> PriceBand:
    return PriceBand(
        id=row["id"],
        category=row["category"],
        tier=row["tier"],
        min_aed=row["min_aed"],
        max_aed=row["max_aed"],
        provenance=row["provenance"],
        source=row["source"],
        as_of=_date(row["as_of"]),
    )


class SqlitePlaceRepo:
    def __init__(self, catalog: SqliteCatalog) -> None:
        self._catalog = catalog

    def get(self, place_id: str) -> Place | None:
        return self._catalog.get_place(place_id)

    def search(
        self,
        *,
        area: str | None = None,
        tag: str | None = None,
        status: str | None = None,
        category: str | None = None,
    ) -> list[Place]:
        return self._catalog.search_places(
            area=area, tag=tag, status=status, category=category
        )


class SqliteRestaurantRepo:
    def __init__(self, catalog: SqliteCatalog) -> None:
        self._catalog = catalog

    def search(
        self,
        *,
        area: str | None = None,
        tier: str | None = None,
        cuisine: str | None = None,
    ) -> list[Restaurant]:
        return self._catalog.search_restaurants(area=area, tier=tier, cuisine=cuisine)


class SqliteHotelRepo:
    def __init__(self, catalog: SqliteCatalog) -> None:
        self._catalog = catalog

    def get(self, hotel_id: str) -> Hotel | None:
        return self._catalog.get_hotel(hotel_id)

    def search(self, *, area: str | None = None, tier: str | None = None) -> list[Hotel]:
        return self._catalog.search_hotels(area=area, tier=tier)


class SqliteTransitRepo:
    def __init__(self, catalog: SqliteCatalog) -> None:
        self._catalog = catalog

    def stations(self, *, line: str | None = None) -> list[TransitStation]:
        return self._catalog.stations(line=line)

    def edges(self, *, line: str | None = None) -> list[TransitEdge]:
        return self._catalog.edges(line=line)


class SqliteFareRepo:
    def __init__(self, catalog: SqliteCatalog) -> None:
        self._catalog = catalog

    def all(self) -> list[Fare]:
        return self._catalog.fares()

    def for_mode(self, mode: str) -> list[Fare]:
        return self._catalog.fares_for_mode(mode)


class SqlitePriceRepo:
    def __init__(self, catalog: SqliteCatalog) -> None:
        self._catalog = catalog

    def bands(
        self,
        *,
        category: str | None = None,
        tier: str | None = None,
    ) -> list[PriceBand]:
        return self._catalog.price_bands(category=category, tier=tier)


class SqliteHolidayRepo:
    def __init__(self, catalog: SqliteCatalog) -> None:
        self._catalog = catalog

    def all(self) -> list[Holiday]:
        return self._catalog.holidays()

    def overlapping(self, start: date, end: date) -> list[Holiday]:
        return self._catalog.holidays_overlapping(start, end)


class SqliteClimateRepo:
    def __init__(self, catalog: SqliteCatalog) -> None:
        self._catalog = catalog

    def month(self, month: int) -> ClimateMonth | None:
        return self._catalog.climate_month(month)

    def all(self) -> list[ClimateMonth]:
        return self._catalog.climate_all()


def _holiday(row: sqlite3.Row) -> Holiday:
    return Holiday(
        id=row["id"],
        name=row["name"],
        kind=row["kind"],
        start=date.fromisoformat(row["start"]),
        end=date.fromisoformat(row["end"]),
        effects=json.loads(row["effects"]),
        notes=row["notes"],
        provenance=row["provenance"],
        source=row["source"],
        as_of=_date(row["as_of"]),
    )


def _climate(row: sqlite3.Row) -> ClimateMonth:
    return ClimateMonth(
        month=row["month"],
        avg_high_c=row["avg_high_c"],
        avg_low_c=row["avg_low_c"],
        rain_mm=row["rain_mm"],
        humidity_pct=row["humidity_pct"],
        provenance=row["provenance"],
        source=row["source"],
        as_of=_date(row["as_of"]),
    )
