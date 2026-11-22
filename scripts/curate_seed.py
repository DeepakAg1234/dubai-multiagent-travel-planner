"""Build data/seed/*.json from the named catalog plus public coordinates.

Nominatim is used one request at a time, with a cache under data/raw/.
Re-running the script reuses that cache. The seed JSON is what the app loads.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

import httpx

from seed_catalog import (
    GREEN,
    HOTEL_COLUMNS,
    HOTELS,
    PLACE_COLUMNS,
    PLACES,
    RED_EXPO,
    RED_LIFE,
    RED_MAIN,
    STATION_COLUMNS,
    TRAM,
    parse_table,
)
from travel_planner.config import REPO_ROOT
from travel_planner.models import (
    ClimateMonth,
    Fare,
    Hotel,
    Place,
    PriceBand,
    PriceRange,
    Restaurant,
    TransitEdge,
    TransitStation,
)

RAW = REPO_ROOT / "data" / "raw"
SEED = REPO_ROOT / "data" / "seed"
UA = "DubaiTravelPlannerCuration/0.1 (educational course project; local curation)"
CURATED_ON = date(2026, 11, 17)
RESEARCH_ON = date(2026, 11, 16)
DUBAI_LAT = (24.75, 25.40)
DUBAI_LNG = (54.85, 55.65)
ANCHORS = {
    "Old Dubai": (25.263, 55.297),
    "Downtown": (25.197, 55.274),
    "Marina / JBR": (25.078, 55.139),
    "Jumeirah": (25.204, 55.238),
    "Al Quoz": (25.145, 55.230),
    "Palm": (25.112, 55.139),
    "Dubai Creek": (25.228, 55.340),
    "Business Bay": (25.185, 55.265),
}
HOUR_SPANS = {
    "always": "24 hours",
    "day": "daylight",
    "08-22": "08:00-22:00",
    "09-17": "09:00-17:00",
    "09-21": "09:00-21:00",
    "10-00": "10:00-00:00",
    "10-02": "10:00-02:00",
    "10-18": "10:00-18:00",
    "10-22": "10:00-22:00",
    "12-02": "12:00-02:00",
    "16-00": "16:00-00:00",
    "18-02": "18:00-02:00",
    "22-04": "22:00-04:00",
}
TIER_BANDS = {
    "budget": ((190.0, 330.0), (140.0, 250.0)),
    "mid": ((430.0, 680.0), (300.0, 520.0)),
    "luxury": ((980.0, 1900.0), (700.0, 1500.0)),
}
COMPARISON_PRICES = {
    "Burj Khalifa At the Top": "AED 189",
    "Sky Views Dubai": "AED 89",
    "The View at The Palm": "AED 115",
    "Ain Dubai": "from AED 145",
}
RTA_FARES = (
    "RTA Nol fare table as recorded in docs/research.md on 2026-11-16. "
    "https://www.rta.ae"
)
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def slug(text: str) -> str:
    lowered = text.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")


def hours_for(code: str) -> dict[str, str]:
    span = HOUR_SPANS[code]
    if code in {"always", "day"}:
        return {"daily": span}
    return {day: span for day in WEEKDAYS}


def meal_hours(meals: str) -> dict[str, str]:
    if meals == "dinner":
        span = "18:00-01:00"
    elif meals == "breakfast,lunch":
        span = "08:00-16:00"
    elif "breakfast" in meals:
        span = "08:00-00:00"
    else:
        span = "12:00-00:00"
    return {day: span for day in WEEKDAYS}


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlng / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def in_dubai(lat: float, lng: float) -> bool:
    return DUBAI_LAT[0] <= lat <= DUBAI_LAT[1] and DUBAI_LNG[0] <= lng <= DUBAI_LNG[1]


def load_json(path: Path, default: object) -> object:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class Geocoder:
    def __init__(self) -> None:
        self.path = RAW / "geocode_cache.json"
        stored = load_json(self.path, {})
        self.cache: dict[str, dict[str, object]] = stored if isinstance(stored, dict) else {}
        self.client = httpx.Client(headers={"User-Agent": UA}, timeout=40)

    def close(self) -> None:
        self.client.close()
        save_json(self.path, self.cache)

    def resolve(
        self,
        queries: list[str],
        *,
        area: str | None,
        limit_km: float,
        bounded_name: str | None = None,
    ) -> tuple[float, float, str]:
        last = "no result"
        for query in queries:
            found = self._try(query, viewbox=None)
            if isinstance(found, str):
                last = found
                continue
            lat, lng, label = found
            too_far = area in ANCHORS and near_anchor(area or "", lat, lng, limit_km)
            if too_far:
                last = f"{too_far} ({query})"
                continue
            return lat, lng, label
        if bounded_name and area in ANCHORS:
            lat0, lng0 = ANCHORS[area]
            viewbox = f"{lng0 - 0.09},{lat0 + 0.07},{lng0 + 0.09},{lat0 - 0.07}"
            found = self._try(bounded_name, viewbox=viewbox)
            if not isinstance(found, str):
                return found
            last = found
        raise LookupError(last)

    def _try(self, query: str, viewbox: str | None) -> tuple[float, float, str] | str:
        try:
            return self._fetch(query, viewbox)
        except httpx.HTTPError as exc:
            time.sleep(8)
            try:
                return self._fetch(query, viewbox)
            except (LookupError, httpx.HTTPError) as retry_exc:
                return str(retry_exc or exc)
        except LookupError as exc:
            return str(exc)

    def _fetch(self, query: str, viewbox: str | None) -> tuple[float, float, str]:
        key = query if not viewbox else f"{query} @ {viewbox}"
        cached = self.cache.get(key)
        if cached:
            return float(cached["lat"]), float(cached["lng"]), str(cached["label"])
        time.sleep(1.1)
        params: dict[str, str | int] = {
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "ae",
        }
        if viewbox:
            params["viewbox"] = viewbox
            params["bounded"] = 1
        response = self.client.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
        )
        response.raise_for_status()
        rows = response.json()
        if not rows:
            raise LookupError(f"no geocode result for {query!r}")
        hit = rows[0]
        lat, lng = float(hit["lat"]), float(hit["lon"])
        label = str(hit.get("display_name", ""))
        if not in_dubai(lat, lng) or not any(token in label for token in ("Dubai", "دبي")):
            raise LookupError(f"{query!r} geocoded outside Dubai: {label}")
        self.cache[key] = {"lat": lat, "lng": lng, "label": label}
        return lat, lng, label


def near_anchor(area: str, lat: float, lng: float, limit_km: float) -> str | None:
    anchor = ANCHORS.get(area)
    if anchor is None:
        return None
    distance = haversine_km(lat, lng, anchor[0], anchor[1])
    if distance > limit_km:
        return f"{distance:.1f} km from the {area} anchor"
    return None


def place_source(row: dict[str, str], coord_note: str) -> str:
    name = row["name"]
    notes: list[str] = []
    if name == "Dubai Frame":
        notes.append(
            "Adult ticket AED 50 verified from https://www.dubaiframe.ae on 2026-11-16 "
            "(docs/research.md). The stored range is the adult ticket, not the AED 20 child ticket."
        )
    elif name == "Museum of the Future":
        notes.append(
            "Closed for an overhaul since early September 2026. Expected to reopen in Q1 2027 "
            "with no date set and no tickets on sale. The last adult price AED 169 is historical, "
            "so provenance stays estimated (docs/research.md, checked 2026-11-16)."
        )
    elif name in COMPARISON_PRICES:
        notes.append(
            f"Adult price {COMPARISON_PRICES[name]} comes from a comparison site recorded in "
            "docs/research.md on 2026-11-16, not from a fresh read of the operator page, "
            "so provenance stays estimated."
        )
    elif name == "Dubai Creek Abra Crossing":
        notes.append(
            "About AED 1 per crossing, recorded as unchecked general knowledge in "
            "docs/research.md on 2026-11-16."
        )
    elif float(row["min"]) == 0 and float(row["max"]) == 0:
        notes.append("Treated as free to enter. That was not re-checked on an official page.")
    else:
        notes.append("Ticket range is an estimate, not an official quote.")
    notes.append(coord_note)
    notes.append("Crowd level, visit length, and opening hours are estimated.")
    return " ".join(notes)


def wiki_coordinates(titles: list[str]) -> dict[str, tuple[float, float]]:
    path = RAW / "wiki_coords.json"
    cache: dict[str, list[float]] = load_json(path, {})  # type: ignore[assignment]
    missing = [title for title in titles if title not in cache]
    if missing:
        with httpx.Client(headers={"User-Agent": UA}, timeout=60) as client:
            for start in range(0, len(missing), 20):
                chunk = missing[start : start + 20]
                response = client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "prop": "coordinates",
                        "titles": "|".join(chunk),
                        "format": "json",
                        "colimit": "50",
                    },
                )
                response.raise_for_status()
                pages = response.json()["query"]["pages"]
                found: set[str] = set()
                for page in pages.values():
                    title = page.get("title")
                    coords = page.get("coordinates") or []
                    if title and coords:
                        cache[title] = [coords[0]["lat"], coords[0]["lon"]]
                        found.add(title)
                for title in chunk:
                    if title not in found and title not in cache:
                        cache[title] = []
                time.sleep(0.4)
        save_json(path, cache)
    located: dict[str, tuple[float, float]] = {}
    for title, pair in cache.items():
        if pair:
            located[title] = (float(pair[0]), float(pair[1]))
    return located


def station_rows(
    table: str,
    line: str,
) -> list[dict[str, str]]:
    rows = []
    for row in parse_table(table, STATION_COLUMNS):
        rows.append({**row, "line": line})
    return rows


def fill_line(
    titles: list[str],
    known: dict[str, tuple[float, float]],
) -> tuple[dict[str, tuple[float, float]], set[str]]:
    """Fill gaps between Wikipedia coordinates. Missing end stations are projected."""
    points: dict[str, tuple[float, float]] = {}
    for title in titles:
        point = known.get(title)
        if point is not None and in_dubai(point[0], point[1]):
            points[title] = point
    interpolated: set[str] = set()

    def indexes() -> list[int]:
        return [index for index, title in enumerate(titles) if title in points]

    known_indexes = indexes()
    for left, right in zip(known_indexes, known_indexes[1:], strict=False):
        lat1, lng1 = points[titles[left]]
        lat2, lng2 = points[titles[right]]
        span = right - left
        for step in range(1, span):
            title = titles[left + step]
            weight = step / span
            points[title] = (lat1 + (lat2 - lat1) * weight, lng1 + (lng2 - lng1) * weight)
            interpolated.add(title)
    known_indexes = indexes()
    if len(known_indexes) >= 2 and known_indexes[0] > 0:
        start, nxt = known_indexes[0], known_indexes[1]
        lat0, lng0 = points[titles[start]]
        lat1, lng1 = points[titles[nxt]]
        step_lat = (lat0 - lat1) / (nxt - start)
        step_lng = (lng0 - lng1) / (nxt - start)
        for index in range(start - 1, -1, -1):
            back = start - index
            points[titles[index]] = (lat0 + step_lat * back, lng0 + step_lng * back)
            interpolated.add(titles[index])
    known_indexes = indexes()
    if len(known_indexes) >= 2 and known_indexes[-1] < len(titles) - 1:
        prev, end = known_indexes[-2], known_indexes[-1]
        lat0, lng0 = points[titles[prev]]
        lat1, lng1 = points[titles[end]]
        step_lat = (lat1 - lat0) / (end - prev)
        step_lng = (lng1 - lng0) / (end - prev)
        for index in range(end + 1, len(titles)):
            forward = index - end
            points[titles[index]] = (lat1 + step_lat * forward, lng1 + step_lng * forward)
            interpolated.add(titles[index])
    return points, interpolated


def build_stations(
    geocoder: Geocoder,
    failures: list[str],
) -> list[TransitStation]:
    wiki_rows = (
        station_rows(RED_MAIN, "Red")
        + station_rows(RED_LIFE, "Red")
        + station_rows(RED_EXPO, "Red")
        + station_rows(GREEN, "Green")
    )
    titles = [row["ref"] for row in wiki_rows]
    coordinates = wiki_coordinates(titles)
    filled = {
        title: (point[0], point[1])
        for title, point in coordinates.items()
        if point and in_dubai(point[0], point[1])
    }
    interpolated: set[str] = set()
    red_titles = [row["ref"] for row in station_rows(RED_MAIN, "Red")]
    life_titles = [row["ref"] for row in station_rows(RED_LIFE, "Red")]
    expo_titles = [row["ref"] for row in station_rows(RED_EXPO, "Red")]
    green_titles = [row["ref"] for row in station_rows(GREEN, "Green")]
    for sequence in (
        red_titles + life_titles[:1],
        red_titles[-1:] + life_titles,
        red_titles[-1:] + expo_titles,
        green_titles,
    ):
        line_points, line_gaps = fill_line(sequence, filled)
        filled.update(line_points)
        interpolated.update(line_gaps)
    merged: dict[str, dict[str, object]] = {}
    for row in wiki_rows:
        title = row["ref"]
        point = filled.get(title)
        if point is None:
            failures.append(f"station {row['name']}: no coordinate")
            continue
        if title in interpolated:
            coord_note = (
                "No Wikipedia coordinate on 2026-11-17. Position estimated between the "
                "neighboring stations that do have one."
            )
            provenance = "estimated"
        else:
            coord_note = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            provenance = "api"
        current = merged.get(title)
        if current is None:
            merged[title] = {
                "name": row["name"],
                "lines": [row["line"]],
                "codes": [f"{row['line'][0]}{row['code']}"],
                "point": point,
                "note": coord_note,
                "provenance": provenance,
            }
        else:
            lines = current["lines"]
            assert isinstance(lines, list)
            if row["line"] not in lines:
                lines.append(row["line"])
            codes = current["codes"]
            assert isinstance(codes, list)
            codes.append(f"{row['line'][0]}{row['code']}")
    stations = [
        TransitStation(
            id=f"metro-{slug(str(item['name']))}",
            name=str(item["name"]),
            line=",".join(item["lines"]),  # type: ignore[arg-type]
            code="/".join(item["codes"]),  # type: ignore[arg-type]
            lat=item["point"][0],  # type: ignore[index]
            lng=item["point"][1],  # type: ignore[index]
            zone=None,
            provenance=item["provenance"],  # type: ignore[arg-type]
            source=(
                "Station order and name from the English Wikipedia Red Line and Green Line "
                f"tables retrieved 2026-11-17. Coordinates: {item['note']}. "
                "RTA fare zone is not on that table, so zone is empty. "
                "Not an RTA GTFS feed."
            ),
            as_of=CURATED_ON,
        )
        for item in merged.values()
    ]
    for row in parse_table(TRAM, STATION_COLUMNS):
        try:
            lat, lng, _label = geocoder.resolve(
                [
                    row["ref"],
                    f"{row['name']} tram stop Dubai",
                    f"Dubai Tram {row['name']}",
                ],
                area="Marina / JBR",
                limit_km=18,
                bounded_name=f"{row['name']} tram",
            )
        except LookupError as exc:
            failures.append(f"tram {row['name']}: {exc}")
            continue
        stations.append(
            TransitStation(
                id=f"tram-{slug(row['name'])}",
                name=row["name"],
                line="Tram",
                code=f"T{row['code']}",
                lat=lat,
                lng=lng,
                zone=None,
                provenance="api",
                source=(
                    "Station order from the English Wikipedia Dubai Tram table retrieved "
                    "2026-11-17, with the 'Jumeriah' spelling corrected. "
                    f"Coordinates: Nominatim query {row['ref']!r}. "
                    "Ride times are estimated."
                ),
                as_of=CURATED_ON,
            )
        )
    return stations


def chain_ids(table: str, prefix: str) -> list[str]:
    return [f"{prefix}{slug(row['name'])}" for row in parse_table(table, STATION_COLUMNS)]


def build_edges(stations: list[TransitStation]) -> list[TransitEdge]:
    by_id = {station.id: station for station in stations}
    red_speed = 36.0
    sequences = [
        ("Red", chain_ids(RED_MAIN, "metro-")),
        ("Red", [chain_ids(RED_MAIN, "metro-")[-1], *chain_ids(RED_LIFE, "metro-")]),
        ("Red", [chain_ids(RED_MAIN, "metro-")[-1], *chain_ids(RED_EXPO, "metro-")]),
        ("Green", chain_ids(GREEN, "metro-")),
    ]
    drafted: list[tuple[str, str, str, float]] = []
    for line, ids in sequences:
        for left, right in zip(ids, ids[1:], strict=False):
            drafted.append((line, left, right, red_speed))
    for line, left, right, _speed in [
        ("Tram", left, right, 18.0)
        for left, right in zip(
            chain_ids(TRAM, "tram-"), chain_ids(TRAM, "tram-")[1:], strict=False
        )
    ]:
        drafted.append((line, left, right, 18.0))
    drafted.append(("walk", "tram-jumeirah-lakes-towers", "metro-dmcc", 0))
    drafted.append(("walk", "tram-dubai-marina", "metro-sobha-realty", 0))

    def hop_minutes(left: str, right: str, speed: float) -> int:
        if speed <= 0:
            return 6
        km = haversine_km(by_id[left].lat, by_id[left].lng, by_id[right].lat, by_id[right].lng)
        return max(2, int(round(km / speed * 60)))

    expo_ids = chain_ids(RED_MAIN, "metro-") + chain_ids(RED_EXPO, "metro-")
    raw_total = sum(
        hop_minutes(left, right, red_speed)
        for left, right in zip(expo_ids, expo_ids[1:], strict=False)
    )
    scale = 74 / raw_total if raw_total else 1
    edges: list[TransitEdge] = []
    for line, left, right, speed in drafted:
        if left not in by_id or right not in by_id:
            raise KeyError(f"missing station for edge {left} -> {right}")
        if speed <= 0:
            minutes = 6
            detail = "Walk interchange estimated at 6 minutes."
        else:
            minutes = max(
                2,
                int(round(hop_minutes(left, right, speed) * (scale if line != "Tram" else 1))),
            )
            detail = (
                "Minutes are estimated from straight-line distance. "
                "Red and Green hops are scaled so Centrepoint to Expo 2020 is about 74 minutes, "
                "the end-to-end time on the Wikipedia Red Line page retrieved 2026-11-17. "
                "This is not an RTA GTFS feed."
            )
        edges.append(
            TransitEdge(
                id=f"{left}__{right}",
                from_id=left,
                to_id=right,
                line=line,
                minutes=minutes,
                provenance="estimated",
                source=detail,
                as_of=CURATED_ON,
            )
        )
    return edges


def ranged(name: str, low: float, high: float) -> tuple[float, float]:
    nudge = (sum(name.encode("utf-8")) % 11) - 5
    return low + nudge * 4, high + nudge * 6


SKIP_PLACES = {
    "Coin Museum",
    "Diving Village",
    "XVA Gallery",
    "Crossroads of Civilizations Museum",
    "Saruq Al Hadid Museum",
    "Black Palace Beach",
    "WHITE Dubai",
    "Blue Marlin Ibiza UAE",
    "Lock Stock and Barrel",
    "OliOli",
}
PLACE_QUERIES = {
    "Al Mamzar Beach Park": ["Al Mamzar Beach"],
    "The Lost Chambers Aquarium": ["Lost Chambers Atlantis"],
    "Dubai Aquarium and Underwater Zoo": ["Dubai Aquarium Dubai Mall"],
}
EXTRA_PLACES = [
    {
        "name": "Dubai Fountain",
        "category": "landmark",
        "area": "Downtown",
        "tags": "landmark,outdoor",
        "min": "0",
        "max": "0",
        "price_class": "estimated",
        "crowd": "high",
        "minutes": "30",
        "hours": "18-02",
        "indoor": "0",
        "timed": "0",
        "status": "open",
        "url": "",
        "query": "Dubai Fountain",
    },
    {
        "name": "Pier 7",
        "category": "venue",
        "area": "Marina / JBR",
        "tags": "nightlife",
        "min": "0",
        "max": "0",
        "price_class": "estimated",
        "crowd": "high",
        "minutes": "150",
        "hours": "12-02",
        "indoor": "0",
        "timed": "0",
        "status": "open",
        "url": "",
        "query": "Pier 7 Dubai Marina",
    },
    {
        "name": "360 Dubai",
        "category": "venue",
        "area": "Jumeirah",
        "tags": "nightlife",
        "min": "0",
        "max": "150",
        "price_class": "estimated",
        "crowd": "medium",
        "minutes": "120",
        "hours": "17-02",
        "indoor": "0",
        "timed": "0",
        "status": "open",
        "url": "",
        "query": "360 bar Burj Al Arab Dubai",
    },
]


def build_places(geocoder: Geocoder, failures: list[str]) -> list[Place]:
    places: list[Place] = []
    rows = [row for row in parse_table(PLACES, PLACE_COLUMNS) if row["name"] not in SKIP_PLACES]
    rows.extend(EXTRA_PLACES)
    for row in rows:
        if "17-02" not in HOUR_SPANS and row["hours"] == "17-02":
            row["hours"] = "18-02"
        queries = PLACE_QUERIES.get(
            row["name"],
            [row["query"] or f"{row['name']} Dubai", f"{row['name']} Dubai"],
        )
        try:
            lat, lng, _label = geocoder.resolve(
                queries,
                area=row["area"],
                limit_km=15,
                bounded_name=row["name"],
            )
        except LookupError as exc:
            failures.append(f"place {row['name']}: {exc}")
            continue
        status_as_of = date(2026, 9, 1) if row["status"] == "reopening" else None
        places.append(
            Place(
                id=f"place-{slug(row['name'])}",
                name=row["name"],
                category=row["category"],
                area=row["area"],
                lat=lat,
                lng=lng,
                tags=[tag for tag in row["tags"].split(",") if tag],
                price_aed=PriceRange(min_aed=float(row["min"]), max_aed=float(row["max"])),
                crowd_level=row["crowd"],  # type: ignore[arg-type]
                typical_visit_minutes=int(row["minutes"]),
                opening_hours=hours_for(row["hours"]),
                indoor=row["indoor"] == "1",
                timed_entry=row["timed"] == "1",
                operational_status=row["status"],  # type: ignore[arg-type]
                status_as_of=status_as_of,
                official_url=row["url"] or None,
                provenance=row["price_class"],  # type: ignore[arg-type]
                source=place_source(row, f"Nominatim query {queries[0]!r} on 2026-11-17."),
                as_of=CURATED_ON,
            )
        )
    return places


class SeedGap(RuntimeError):
    pass


def build_restaurants(geocoder: Geocoder, failures: list[str]) -> list[Restaurant]:
    del geocoder, failures
    payload = json.loads((RAW / "gap_search.json").read_text(encoding="utf-8"))
    tiers = ("budget", "budget", "mid", "mid", "upscale")
    restaurants: list[Restaurant] = []
    for area, anchor in ANCHORS.items():
        chosen: list[dict[str, object]] = []
        seen: set[str] = set()
        for row in payload["restaurants"][area]:
            name = str(row.get("name") or "").strip()
            if len(name) < 3 or name.casefold() in {"restaurant", "cafe", "hotel"}:
                continue
            key = name.casefold()
            if key in seen:
                continue
            lat, lng = float(row["lat"]), float(row["lon"])
            if haversine_km(lat, lng, anchor[0], anchor[1]) > 6:
                continue
            seen.add(key)
            chosen.append(row)
            if len(chosen) == 10:
                break
        if len(chosen) < 6:
            raise SeedGap(f"{area} only has {len(chosen)} named restaurants within 6 km")
        for index, row in enumerate(chosen):
            name = str(row["name"])
            tier = tiers[index % len(tiers)]
            restaurants.append(
                Restaurant(
                    id=f"restaurant-{slug(area)}-{slug(name)}",
                    name=name,
                    cuisine="unspecified",
                    area=area,
                    lat=float(row["lat"]),
                    lng=float(row["lon"]),
                    price_band=tier,  # type: ignore[arg-type]
                    meal_types=["lunch", "dinner"],
                    opening_hours=meal_hours("lunch,dinner"),
                    price_aed=None,
                    provenance="estimated",
                    source=(
                        "Name and coordinates from a Nominatim search for restaurants inside "
                        f"6 km of the {area} anchor on 2026-11-17. OpenStreetMap data, ODbL. "
                        "Cuisine is unspecified and the price band is estimated. No menu price "
                        "was recorded. Overpass was unavailable during curation."
                    ),
                    as_of=CURATED_ON,
                )
            )
    return restaurants


def build_hotels(
    geocoder: Geocoder,
    stations: list[TransitStation],
    failures: list[str],
) -> list[Hotel]:
    hotels: list[Hotel] = []
    for row in parse_table(HOTELS, HOTEL_COLUMNS):
        try:
            lat, lng, _label = geocoder.resolve(
                [row["query"], f"{row['name']} Dubai"],
                area=None,
                limit_km=99,
            )
        except LookupError as exc:
            failures.append(f"hotel {row['name']}: {exc}")
            continue
        distances = {
            area: haversine_km(lat, lng, anchor[0], anchor[1]) for area, anchor in ANCHORS.items()
        }
        nearest = min(distances, key=distances.get)
        if distances[row["area"]] <= 12:
            area = row["area"]
        elif distances[nearest] <= 8:
            area = nearest
        else:
            failures.append(f"hotel {row['name']}: {distances[nearest]:.1f} km from every anchor")
            continue
        nearest_name = None
        nearest_km = 1.5
        for station in stations:
            distance = haversine_km(lat, lng, station.lat, station.lng)
            if distance <= nearest_km:
                nearest_name = station.name
                nearest_km = distance
        peak, summer = TIER_BANDS[row["tier"]]
        peak_min, peak_max = ranged(row["name"], *peak)
        summer_min, summer_max = ranged(row["name"] + " summer", *summer)
        hotels.append(
            Hotel(
                id=f"hotel-{slug(row['name'])}",
                name=row["name"],
                area=area,
                tier=row["tier"],  # type: ignore[arg-type]
                lat=lat,
                lng=lng,
                stars=None,
                metro_nearby=nearest_name,
                official_url=None,
                peak_nightly_min=peak_min,
                peak_nightly_max=peak_max,
                summer_nightly_min=summer_min,
                summer_nightly_max=summer_max,
                provenance="estimated",
                source=(
                    f"Hotel identity geocoded with Nominatim query {row['query']!r} on 2026-11-17. "
                    "Peak and summer nightly ranges are the shared tier band in docs/research.md "
                    "section 5.1, nudged so rows are not identical. They are not a quote from "
                    "the hotel's website. Star rating was not re-checked, so it is omitted. "
                    + (
                        f"Nearest curated station within 1.5 km: {nearest_name}."
                        if nearest_name
                        else "No curated station within 1.5 km."
                    )
                ),
                as_of=CURATED_ON,
            )
        )
    supplement_hotels(hotels)
    return hotels


def supplement_hotels(hotels: list[Hotel]) -> None:
    """Add the nearest named hotel when a planning area is missing a tier."""
    payload = json.loads((RAW / "gap_search.json").read_text(encoding="utf-8"))
    used = {hotel.name.casefold() for hotel in hotels}
    luxury_words = (
        "address",
        "sofitel",
        "fairmont",
        "armani",
        "raffles",
        "palace",
        "atlantis",
        "mandarin",
        "conrad",
        "hyatt",
        "grand cosmopolitan",
    )
    budget_words = (
        "ibis",
        "premier inn",
        "holiday inn",
        "rove",
        "citymax",
        "hampton",
        "hafez",
        "majestic",
    )
    for area in ANCHORS:
        present = {hotel.tier for hotel in hotels if hotel.area == area}
        for tier in ("budget", "mid", "luxury"):
            if tier in present:
                continue
            anchor = ANCHORS[area]
            best: tuple[float, dict[str, object]] | None = None
            for rows in payload["hotels"].values():
                for row in rows:
                    name = str(row.get("name") or "").strip()
                    if len(name) < 4 or name.casefold() in used or name.casefold() in {"hotel"}:
                        continue
                    lat, lng = float(row["lat"]), float(row["lon"])
                    distance = haversine_km(lat, lng, anchor[0], anchor[1])
                    if distance > 6:
                        continue
                    lowered = name.casefold()
                    if tier == "luxury" and not any(word in lowered for word in luxury_words):
                        continue
                    if tier == "budget" and not any(word in lowered for word in budget_words):
                        continue
                    if tier == "mid" and any(
                        word in lowered for word in luxury_words + budget_words
                    ):
                        continue
                    if best is None or distance < best[0]:
                        best = (distance, row)
            if best is None and tier == "luxury":
                continue
            if best is None:
                continue
            distance, row = best
            name = str(row["name"])
            peak, summer = TIER_BANDS[tier]
            peak_min, peak_max = ranged(name, *peak)
            summer_min, summer_max = ranged(name + " summer", *summer)
            hotels.append(
                Hotel(
                    id=f"hotel-{slug(name)}",
                    name=name,
                    area=area,
                    tier=tier,  # type: ignore[arg-type]
                    lat=float(row["lat"]),
                    lng=float(row["lon"]),
                    stars=None,
                    metro_nearby=None,
                    official_url=None,
                    peak_nightly_min=peak_min,
                    peak_nightly_max=peak_max,
                    summer_nightly_min=summer_min,
                    summer_nightly_max=summer_max,
                    provenance="estimated",
                    source=(
                        f"Nearest named hotel in a Nominatim area search, "
                        f"{distance:.1f} km from the {area} anchor, added because the named "
                        f"shortlist had no {tier} property with a usable pin. Nightly range is "
                        "the shared tier band in docs/research.md section 5.1, not a hotel quote."
                    ),
                    as_of=CURATED_ON,
                )
            )
            used.add(name.casefold())
            present.add(tier)


def build_fares() -> list[Fare]:
    verified = "verified"
    estimated = "estimated"
    rows = [
        ("metro-silver-1", "metro", "1", 3, "silver", verified, "One zone, Silver Nol."),
        ("metro-silver-2", "metro", "2", 5, "silver", verified, "Two adjacent zones, Silver Nol."),
        ("metro-silver-3plus", "metro", "3+", 7.5, "silver", verified, "More than two zones."),
        ("metro-gold-1", "metro", "1", 6, "gold", verified, "One zone, Gold Nol."),
        ("metro-gold-2", "metro", "2", 10, "gold", verified, "Two zones, Gold Nol."),
        ("metro-gold-3plus", "metro", "3+", 15, "gold", verified, "More than two zones, Gold Nol."),
        ("metro-red-1", "metro", "1", 4, "red", verified, "One zone, Red Ticket."),
        ("metro-red-2", "metro", "2", 6, "red", verified, "Two zones, Red Ticket."),
        ("metro-red-3plus", "metro", "3+", 8.5, "red", verified, "More than two zones."),
        (
            "pass-silver-7day-1",
            "metro",
            "1",
            50,
            "silver_7day",
            verified,
            "7-day pass, one zone, Silver.",
        ),
        (
            "pass-silver-7day-2",
            "metro",
            "2",
            80,
            "silver_7day",
            verified,
            "7-day pass, two zones, Silver.",
        ),
        (
            "pass-silver-7day-all",
            "metro",
            "all",
            110,
            "silver_7day",
            verified,
            "7-day pass, all zones, Silver.",
        ),
        (
            "nol-silver-card",
            "nol_card",
            "purchase",
            25,
            "silver",
            verified,
            "Silver card price. AED 19 of the AED 25 is stored credit.",
        ),
        (
            "pass-1day",
            "metro",
            "all",
            20,
            "red_1day",
            estimated,
            "1-day Travel Pass quoted at about AED 20 on a Red Ticket. "
            "docs/research.md could not confirm this on the RTA fare table.",
        ),
        (
            "nol-red-card",
            "nol_card",
            "purchase",
            2,
            "red",
            estimated,
            "Red Ticket price from a third-party figure in docs/research.md, not the RTA table.",
        ),
        (
            "taxi-flag-day",
            "taxi",
            "flag_06_22",
            5,
            "street_hail",
            estimated,
            "Daytime street-hail flag fall. The research notes disagree, so this stays estimated.",
        ),
        (
            "taxi-flag-night",
            "taxi",
            "flag_22_06",
            5.5,
            "street_hail",
            estimated,
            "Night street-hail flag fall. Estimated from the same unchecked tariff notes.",
        ),
        (
            "taxi-per-km",
            "taxi",
            "per_km",
            2.45,
            "street_hail",
            estimated,
            "Higher of the two per-km rates in docs/research.md. Use AED 2.45 for budgeting.",
        ),
        (
            "taxi-minimum",
            "taxi",
            "minimum",
            12,
            "street_hail",
            estimated,
            "Street-hail minimum fare. Estimated.",
        ),
        (
            "abra-crossing",
            "ferry",
            "fixed",
            1,
            "cash",
            estimated,
            "Abra crossing, about AED 1. Not rechecked on an RTA page.",
        ),
    ]
    return [
        Fare(
            id=item[0],
            mode=item[1],
            zone_rule=item[2],
            price_aed=item[3],
            card_type=item[4],
            provenance=item[5],  # type: ignore[arg-type]
            notes=item[6],
            source=RTA_FARES,
            as_of=RESEARCH_ON,
        )
        for item in rows
    ]


def build_price_bands() -> list[PriceBand]:
    source = (
        "Observed menu bands and the RTA taxi notes in docs/research.md, checked 2026-11-16. "
        "These bands price an unnamed meal or a typical extra. They are not a quoted bill."
    )
    rows = [
        ("food", "budget", 25, 45),
        ("food", "mid", 70, 140),
        ("food", "upscale", 180, 400),
        ("coffee", "any", 12, 28),
        ("water", "any", 2, 8),
        ("activity", "free", 0, 0),
        ("activity", "budget", 20, 60),
        ("activity", "mid", 70, 180),
        ("activity", "upscale", 180, 400),
        ("taxi_trip", "typical", 12, 45),
    ]
    return [
        PriceBand(
            id=f"band-{category}-{tier}",
            category=category,
            tier=tier,
            min_aed=low,
            max_aed=high,
            provenance="estimated",
            source=source,
            as_of=RESEARCH_ON,
        )
        for category, tier, low, high in rows
    ]


def build_climate() -> list[ClimateMonth]:
    path = RAW / "climate_daily.json"
    if not path.is_file():
        with httpx.Client(headers={"User-Agent": UA}, timeout=180) as client:
            response = client.get(
                "https://archive-api.open-meteo.com/v1/archive",
                params={
                    "latitude": 25.2048,
                    "longitude": 55.2708,
                    "start_date": "2016-01-01",
                    "end_date": "2025-12-31",
                    "daily": (
                        "temperature_2m_max,temperature_2m_min,"
                        "precipitation_sum,relative_humidity_2m_mean"
                    ),
                    "timezone": "Asia/Dubai",
                },
            )
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response.content)
    daily = json.loads(path.read_text(encoding="utf-8"))["daily"]
    buckets: dict[int, dict[str, list[float]]] = defaultdict(
        lambda: {"high": [], "low": [], "rain": [], "humidity": []}
    )
    years: set[str] = set()
    for day, high, low, rain, humidity in zip(
        daily["time"],
        daily["temperature_2m_max"],
        daily["temperature_2m_min"],
        daily["precipitation_sum"],
        daily["relative_humidity_2m_mean"],
        strict=True,
    ):
        month = int(day[5:7])
        years.add(day[:4])
        if high is not None:
            buckets[month]["high"].append(high)
        if low is not None:
            buckets[month]["low"].append(low)
        if rain is not None:
            buckets[month]["rain"].append(rain)
        if humidity is not None:
            buckets[month]["humidity"].append(humidity)
    year_count = len(years) or 1
    source = (
        "Open-Meteo archive (CC BY 4.0), daily observations from 2016-01-01 to 2025-12-31 "
        "at 25.2048, 55.2708, averaged by month on 2026-11-17. Climatology, not a forecast. "
        "https://open-meteo.com/"
    )
    rows: list[ClimateMonth] = []
    for month in range(1, 13):
        bucket = buckets[month]
        rows.append(
            ClimateMonth(
                month=month,
                avg_high_c=round(sum(bucket["high"]) / len(bucket["high"]), 1),
                avg_low_c=round(sum(bucket["low"]) / len(bucket["low"]), 1),
                rain_mm=round(sum(bucket["rain"]) / year_count, 1),
                humidity_pct=round(sum(bucket["humidity"]) / len(bucket["humidity"]), 1),
                provenance="estimated",
                source=source,
                as_of=CURATED_ON,
            )
        )
    return rows


def dump(name: str, rows: list[object]) -> None:
    payload = [row.model_dump(mode="json") for row in rows]  # type: ignore[attr-defined]
    save_json(SEED / name, payload)


def main() -> None:
    failures: list[str] = []
    geocoder = Geocoder()
    try:
        places = build_places(geocoder, failures)
        restaurants = build_restaurants(geocoder, failures)
        stations = build_stations(geocoder, failures)
        hotels = build_hotels(geocoder, stations, failures)
    finally:
        geocoder.close()
    if any(item.startswith(("station ", "tram ")) for item in failures):
        print(f"{len(failures)} lookup problems:")
        for item in failures:
            print("-", item)
        raise SystemExit(1)
    if failures:
        print(f"skipped {len(failures)} rows that had no usable pin")
    edges = build_edges(stations)
    fares = build_fares()
    bands = build_price_bands()
    climate = build_climate()
    SEED.mkdir(parents=True, exist_ok=True)
    dump("places.json", places)
    dump("restaurants.json", restaurants)
    dump("hotels.json", hotels)
    dump("transit_stations.json", stations)
    dump("transit_edges.json", edges)
    dump("fares.json", fares)
    dump("price_bands.json", bands)
    dump("climate.json", climate)
    print(
        f"wrote seed: places={len(places)} restaurants={len(restaurants)} "
        f"hotels={len(hotels)} stations={len(stations)} edges={len(edges)}"
    )


if __name__ == "__main__":
    main()
