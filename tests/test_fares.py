"""Silver Nol, taxi floor, Abra, and the offline transit graph."""

from datetime import time

from travel_planner.models import Place
from travel_planner.rules.fares import (
    TransitGraph,
    choose_transit_pass,
    is_abra_crossing,
    nol_zone_for_area,
    route_leg,
    silver_metro_fare,
    taxi_fare_aed,
    zone_span,
)


def _place(place_id: str, area: str, lat: float, lng: float) -> Place:
    return Place(
        id=place_id,
        name=place_id,
        category="landmark",
        area=area,
        lat=lat,
        lng=lng,
        provenance="estimated",
        source="test",
    )


def test_area_zone_map_is_estimated_and_ignores_empty_station_zones(seed) -> None:
    assert nol_zone_for_area("Old Dubai") == 1
    assert nol_zone_for_area("Downtown") == 2
    assert nol_zone_for_area("Marina / JBR") == 3
    assert all(station.zone in {None, ""} for station in seed.stations)


def test_silver_fares_match_verified_nol_table(seed) -> None:
    assert silver_metro_fare(seed.fares, 1).price_aed == 3
    assert silver_metro_fare(seed.fares, 2).price_aed == 5
    assert silver_metro_fare(seed.fares, 3).price_aed == 7.5
    assert silver_metro_fare(seed.fares, 1).provenance == "verified"


def test_seven_day_pass_beats_pay_per_trip_on_many_rides(seed) -> None:
    trips = [7.5] * 20
    plan = choose_transit_pass(trips, days=7, span=3, fares=seed.fares, travelers=1)
    assert plan.choice == "silver_7day"
    assert plan.total_aed == 110
    assert plan.pay_per_trip_aed == 150
    short = choose_transit_pass([3, 3], days=1, span=1, fares=seed.fares)
    assert short.choice == "pay_per_trip"
    assert short.total_aed == 6


def test_one_day_pass_is_estimated_and_beats_six_silver_trips(seed) -> None:
    plan = choose_transit_pass([5] * 6, days=1, span=2, fares=seed.fares)
    assert plan.choice == "red_1day"
    assert plan.total_aed == 20
    assert plan.provenance == "estimated"


def test_taxi_uses_the_minimum_floor_and_night_flag(seed) -> None:
    day, _ = taxi_fare_aed(seed.fares, 0.4, time(14, 0))
    assert day == 12
    night, flag = taxi_fare_aed(seed.fares, 10, time(23, 0))
    assert flag.price_aed == 5.5
    assert night == round(5.5 + 2.45 * 10, 2)
    assert night > 12


def test_abra_when_both_ends_are_creek_waterfront(seed) -> None:
    gold = next(row for row in seed.places if row.id == "place-gold-souk")
    abra = next(row for row in seed.places if row.id == "place-dubai-creek-abra-crossing")
    assert is_abra_crossing(gold.area, abra.area, 0.5)
    graph = TransitGraph(seed.stations, seed.edges)
    leg = route_leg(gold, abra, graph, seed.fares, prefer="ferry")
    assert leg.mode == "ferry"
    assert leg.cost_aed == 1


def test_walk_interchange_is_six_minutes(seed) -> None:
    graph = TransitGraph(seed.stations, seed.edges)
    minutes, lines = graph.minutes("tram-jumeirah-lakes-towers", "metro-dmcc")
    assert minutes == 6
    assert "walk" in lines
    reverse, _ = graph.minutes("metro-dmcc", "tram-jumeirah-lakes-towers")
    assert reverse == 6


def test_union_connects_red_and_green(seed) -> None:
    graph = TransitGraph(seed.stations, seed.edges)
    path = graph.minutes("metro-centrepoint", "metro-e-and")
    assert path is not None
    minutes, _ = path
    assert minutes > 0


def test_short_hop_is_a_walk(seed) -> None:
    left = _place("a", "Downtown", 25.197, 55.274)
    right = _place("b", "Downtown", 25.198, 55.275)
    leg = route_leg(left, right, TransitGraph(seed.stations, seed.edges), seed.fares)
    assert leg.mode == "walk"
    assert leg.cost_aed == 0


def test_zone_span_uses_planning_areas_not_station_zone() -> None:
    assert zone_span(nol_zone_for_area("Old Dubai"), nol_zone_for_area("Palm")) == 3
