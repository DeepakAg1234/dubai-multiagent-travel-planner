"""Local tool wrappers. No network and no LLM."""

from datetime import date

from travel_planner.data.local.sqlite import SqliteCatalog, build_database
from travel_planner.tools.catalog import CatalogTools


def test_search_and_fares_use_the_catalog(tmp_path, seed):
    path = tmp_path / "dubai.sqlite"
    build_database(seed, path)
    tools = CatalogTools(SqliteCatalog(path))

    culture = tools.search_attractions(area="Old Dubai", tag="culture", status="open")
    assert culture.data
    assert all(row.operational_status == "open" for row in culture.data)
    assert all("culture" in row.tags for row in culture.data)

    meals = tools.search_restaurants(
        area="Old Dubai",
        price_band="budget",
        meal_types=["lunch"],
    )
    assert meals.data
    assert all(row.price_band == "budget" for row in meals.data)
    assert all("lunch" in row.meal_types for row in meals.data)
    assert all(row.cuisine == "unspecified" for row in meals.data)

    hotels = tools.search_hotels(area="Old Dubai", tier="budget")
    assert any(row.metro_nearby for row in hotels.data)

    silver = tools.fare_calculator(mode="metro", span=1)
    assert silver.data == 3
    assert silver.provenance == "verified"

    weather = tools.get_weather(7)
    assert weather.data.avg_high_c == 41

    holidays = tools.holiday_lookup(date(2026, 3, 19), date(2026, 3, 19))
    assert any(row.kind == "eid" for row in holidays.data)

    origin = culture.data[0]
    dest = culture.data[1]
    leg = tools.route_between(origin.id, dest.id)
    assert leg.error is None
    assert leg.data.minutes >= 0

    options = tools.get_transport_options().data
    assert {option.mode for option in options} >= {"metro", "taxi", "ferry"}
