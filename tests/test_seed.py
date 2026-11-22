"""The committed seed meets the Phase 1 floors and round-trips through SQLite."""

from datetime import date

from travel_planner.data.areas import PLANNING_AREAS
from travel_planner.data.local import (
    SqliteClimateRepo,
    SqliteFareRepo,
    SqliteHolidayRepo,
    SqliteHotelRepo,
    SqlitePlaceRepo,
    SqlitePriceRepo,
    SqliteRestaurantRepo,
    SqliteTransitRepo,
    build_database,
)
from travel_planner.data.local.sqlite import SqliteCatalog
from travel_planner.data.seed import load_seed


def test_seed_covers_every_planning_area() -> None:
    bundle = load_seed()
    areas = {place.area for place in bundle.places}
    assert set(PLANNING_AREAS) <= areas
    future = next(place for place in bundle.places if "future" in place.id)
    assert future.operational_status == "reopening"
    assert future.status_as_of is not None
    assert len(bundle.climate) == 12
    july = next(row for row in bundle.climate if row.month == 7)
    assert july.avg_high_c > july.avg_low_c
    assert july.avg_high_c > 35


def test_repositories_filter_area_tag_tier_and_status(tmp_path) -> None:
    bundle = load_seed()
    database = tmp_path / "dubai.sqlite"
    build_database(bundle, database)
    catalog = SqliteCatalog(database)
    try:
        places = SqlitePlaceRepo(catalog)
        closed = places.search(status="reopening")
        assert closed and all(place.operational_status == "reopening" for place in closed)
        culture = places.search(area="Old Dubai", tag="culture")
        assert culture
        assert all(place.area == "Old Dubai" and "culture" in place.tags for place in culture)
        assert places.get(culture[0].id) == culture[0]

        restaurants = SqliteRestaurantRepo(catalog)
        budget_meals = restaurants.search(area="Downtown", tier="budget")
        assert budget_meals
        assert all(row.price_band == "budget" for row in budget_meals)

        hotels = SqliteHotelRepo(catalog)
        for area in PLANNING_AREAS:
            for tier in ("budget", "mid", "luxury"):
                found = hotels.search(area=area, tier=tier)
                assert found, f"{area} {tier}"

        transit = SqliteTransitRepo(catalog)
        red = transit.stations(line="Red")
        assert any(station.line == "Red" for station in red)
        assert any("Green" in station.line for station in transit.stations(line="Green"))
        assert transit.edges(line="Red")

        fares = SqliteFareRepo(catalog)
        silver = fares.for_mode("metro")
        assert any(fare.card_type == "silver" and fare.price_aed == 3 for fare in silver)

        bands = SqlitePriceRepo(catalog)
        food = bands.bands(category="food", tier="budget")
        assert food and food[0].max_aed >= food[0].min_aed

        climate = SqliteClimateRepo(catalog)
        assert climate.month(1) is not None
        assert len(climate.all()) == 12

        holidays = SqliteHolidayRepo(catalog)
        assert len(holidays.all()) == len(bundle.holidays)
        national = holidays.overlapping(date(2026, 12, 2), date(2026, 12, 2))
        assert any(row.id == "national-day-2026" for row in national)
        assert holidays.overlapping(date(2026, 11, 18), date(2026, 11, 18)) == []
    finally:
        catalog.close()
