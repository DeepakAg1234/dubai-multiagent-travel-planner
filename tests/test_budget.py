"""Accommodation, food, activity, pass, floor, and alternatives."""

from datetime import date, time

from travel_planner.models import (
    Constraints,
    DayPlan,
    Itinerary,
    Leg,
    Slot,
)
from travel_planner.rules.budget import (
    accommodation_line,
    activity_lines,
    compute_budget,
    food_lines,
    minimum_trip_floor,
    season_for,
    stay_nightly_mid,
)
from travel_planner.rules.fares import TransitGraph
from travel_planner.rules.holidays import effects_on, restaurants_for_day


def test_summer_versus_peak_hotel_midpoint(seed) -> None:
    hotel = next(row for row in seed.hotels if row.id == "hotel-avani-palm-view")
    assert season_for(date(2026, 7, 1)) == "summer"
    assert season_for(date(2026, 11, 18)) == "peak"
    peak = hotel.stay_option("peak")
    summer = hotel.stay_option("summer")
    assert stay_nightly_mid(peak) == (170 + 300) / 2
    assert stay_nightly_mid(summer) < stay_nightly_mid(peak)
    line = accommodation_line(peak, 4)
    assert line.total_aed == stay_nightly_mid(peak) * 4
    assert line.provenance == "estimated"


def test_cheapest_catalog_nights_match_the_locked_floor(seed) -> None:
    peak = min(row.peak_nightly_min for row in seed.hotels if row.tier == "budget")
    summer = min(row.summer_nightly_min for row in seed.hotels if row.tier == "budget")
    assert peak == 170
    assert summer == 120


def test_food_uses_price_bands_and_ramadan_drops_lunch(seed) -> None:
    restaurant = next(row for row in seed.restaurants if row.area == "Old Dubai")
    both = food_lines([restaurant], seed.price_bands, travelers=1)
    assert len(both) == 1
    assert both[0].quantity == 2
    effects = effects_on(seed.holidays, date(2026, 2, 18))
    remaining = restaurants_for_day([restaurant], effects)
    lunchless = food_lines(remaining, seed.price_bands, travelers=1)
    assert lunchless[0].quantity == 1
    band = next(
        row
        for row in seed.price_bands
        if row.category == "food" and row.tier == restaurant.price_band
    )
    assert lunchless[0].unit_aed == (band.min_aed + band.max_aed) / 2


def test_free_place_still_emits_a_zero_activity_line(seed) -> None:
    free = next(row for row in seed.places if row.price_aed and row.price_aed.max_aed == 0)
    lines = activity_lines([free], travelers=2)
    assert lines[0].total_aed == 0
    assert lines[0].provenance == free.provenance
    future = next(row for row in seed.places if row.id == "place-museum-of-the-future")
    assert activity_lines([future], 1) == []


def test_four_peak_nights_at_400_is_below_the_hotel_floor(seed) -> None:
    floor = minimum_trip_floor(
        nights=4,
        days=4,
        travelers=1,
        season="peak",
        hotels=seed.hotels,
        bands=seed.price_bands,
        buffer_pct=10,
    )
    assert floor > 400
    ok = minimum_trip_floor(
        nights=4,
        days=4,
        travelers=1,
        season="peak",
        hotels=seed.hotels,
        bands=seed.price_bands,
        buffer_pct=10,
    )
    assert ok < 5000


def test_compute_budget_picks_passes_and_builds_catalog_alternatives(seed) -> None:
    hotel = next(row for row in seed.hotels if row.id == "hotel-raffles-dubai")
    stay = hotel.stay_option("peak")
    museum = next(row for row in seed.places if row.id == "place-dubai-museum")
    dinner = next(
        row for row in seed.restaurants if row.area == "Old Dubai" and row.price_band == "upscale"
    )
    itinerary = Itinerary(
        stay=stay,
        days=[
            DayPlan(
                day=1,
                theme="Old Dubai",
                slots=[
                    Slot(start=time(10, 0), end=time(11, 30), place_id=museum.id, kind="activity"),
                    Slot(
                        start=time(19, 0),
                        end=time(20, 15),
                        place_id=dinner.id,
                        kind="meal",
                        notes="dinner",
                    ),
                ],
                legs=[
                    Leg(
                        from_id=museum.id,
                        to_id=dinner.id,
                        mode="taxi",
                        minutes=15,
                        distance_km=4,
                        cost_aed=20,
                        provenance="estimated",
                        source="test",
                    ),
                    Leg(
                        from_id=museum.id,
                        to_id=dinner.id,
                        mode="metro",
                        minutes=12,
                        distance_km=3,
                        cost_aed=5,
                        provenance="verified",
                        source="rta",
                    ),
                    Leg(
                        from_id=museum.id,
                        to_id=dinner.id,
                        mode="walk",
                        minutes=6,
                        distance_km=0.4,
                        cost_aed=0,
                        provenance="estimated",
                        source="test",
                    ),
                ],
            )
        ],
    )
    constraints = Constraints(
        days=4,
        budget_aed=20000,
        travelers=1,
        interests=["culture"],
        hotel_tier="luxury",
        start_date=date(2026, 11, 18),
    )
    report = compute_budget(
        itinerary,
        constraints,
        places={museum.id: museum},
        restaurants={dinner.id: dinner, **{row.id: row for row in seed.restaurants}},
        hotels=seed.hotels,
        bands=seed.price_bands,
        fares=seed.fares,
        buffer_pct=10,
        graph=TransitGraph(seed.stations, seed.edges),
    )
    assert report.by_category["accommodation"] > 0
    assert report.by_category["food"] > 0
    assert report.by_category["activities"] == museum.price_aed.max_aed
    assert report.by_category["buffer"] > 0
    assert report.within_budget is True
    kinds = {alt.kind for alt in report.alternatives}
    assert "cheaper_hotel" in kinds
    assert "cheaper_dinner" in kinds
    assert "taxi_to_metro" in kinds or "paid_to_free" in kinds


def test_tight_budget_reports_the_floor_instead_of_a_zero_plan(seed) -> None:
    hotel = next(row for row in seed.hotels if row.tier == "budget")
    stay = hotel.stay_option("peak")
    place = next(row for row in seed.places if row.operational_status == "open")
    itinerary = Itinerary(
        stay=stay,
        days=[
            DayPlan(
                day=1,
                theme="x",
                slots=[
                    Slot(start=time(10, 0), end=time(11, 0), place_id=place.id, kind="activity")
                ],
            )
        ],
    )
    report = compute_budget(
        itinerary,
        Constraints(days=4, budget_aed=400, start_date=date(2026, 1, 10)),
        places={place.id: place},
        restaurants={},
        hotels=seed.hotels,
        bands=seed.price_bands,
        fares=seed.fares,
    )
    assert report.within_budget is False
    assert any(alt.kind == "other" and alt.new_total_aed > 400 for alt in report.alternatives)
    assert report.total_aed > 0
