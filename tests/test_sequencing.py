"""Clustering, holiday filters, heat rest, and timed-entry notes."""

from datetime import date, time

from travel_planner.models import ClimateMonth, Constraints
from travel_planner.rules.holidays import effects_on, places_for_day
from travel_planner.rules.sequencing import (
    cluster_area,
    group_by_day,
    sequence_itinerary,
)


def _climate(month: int, high: float) -> ClimateMonth:
    return ClimateMonth(
        month=month,
        avg_high_c=high,
        avg_low_c=20,
        rain_mm=0,
        humidity_pct=50,
        provenance="estimated",
        source="test",
        as_of=date(2026, 11, 17),
    )


def test_business_bay_merges_with_downtown(seed) -> None:
    bay = [row for row in seed.places if row.area == "Business Bay"]
    assert len(bay) == 3
    assert cluster_area("Business Bay") == "Downtown"
    groups = group_by_day(bay, days=2, pool=[row for row in seed.places if row.area == "Downtown"])
    assert len(groups) == 2
    assert all(len(group) >= 1 for group in groups)
    assert all(cluster_area(place.area) == "Downtown" for group in groups for place in group)


def test_sequence_business_bay_day_is_merged(seed) -> None:
    bay = [row for row in seed.places if row.area == "Business Bay"]
    meals = [row for row in seed.restaurants if row.area in {"Business Bay", "Downtown"}]
    plan = sequence_itinerary(
        bay,
        meals,
        Constraints(days=1, budget_aed=5000, start_date=date(2026, 11, 18)),
        stations=seed.stations,
        edges=seed.edges,
        fares=seed.fares,
        place_pool=seed.places,
        holidays=seed.holidays,
        stay=next(row for row in seed.hotels if row.area == "Downtown").stay_option("peak"),
    )
    assert plan.days[0].theme.startswith("Downtown")
    assert any(slot.kind == "activity" for slot in plan.days[0].slots)
    activity_ids = [slot.place_id for slot in plan.days[0].slots if slot.kind == "activity"]
    assert activity_ids


def test_ramadan_lunch_is_dropped(seed) -> None:
    culture = [
        row for row in seed.places if row.area == "Old Dubai" and row.operational_status == "open"
    ][:4]
    meals = [row for row in seed.restaurants if row.area == "Old Dubai"]
    plan = sequence_itinerary(
        culture,
        meals,
        Constraints(days=1, start_date=date(2026, 2, 18), interests=["culture"]),
        holidays=seed.holidays,
        stations=seed.stations,
        edges=seed.edges,
        fares=seed.fares,
        stay=next(h for h in seed.hotels if h.area == "Old Dubai").stay_option("peak"),
    )
    notes = " ".join(slot.notes or "" for slot in plan.days[0].slots if slot.kind == "meal")
    assert "lunch" not in notes
    assert "dinner" in notes
    assert plan.days[0].holiday_note is not None
    assert effects_on(seed.holidays, date(2026, 2, 18)).drop_lunch


def test_eid_first_day_holds_heritage_later_day_keeps_museums(seed) -> None:
    museum = next(row for row in seed.places if row.id == "place-dubai-museum")
    first = places_for_day(
        [museum], effects_on(seed.holidays, date(2026, 3, 19)), avoid_crowds=False
    )
    later = places_for_day(
        [museum], effects_on(seed.holidays, date(2026, 3, 20)), avoid_crowds=False
    )
    assert first == []
    assert later == [museum]
    meals = [row for row in seed.restaurants if row.area == "Old Dubai"]
    beach = next(row for row in seed.places if row.id == "place-kite-beach")
    plan = sequence_itinerary(
        [museum, beach],
        meals,
        Constraints(days=1, start_date=date(2026, 3, 19), avoid_crowds=False),
        holidays=seed.holidays,
        place_pool=seed.places,
        stations=seed.stations,
        edges=seed.edges,
        fares=seed.fares,
        stay=next(h for h in seed.hotels if h.area == "Jumeirah").stay_option("peak"),
    )
    ids = [slot.place_id for slot in plan.days[0].slots if slot.kind == "activity"]
    assert museum.id not in ids


def test_national_day_drops_crowded_categories_when_avoiding_crowds(seed) -> None:
    mall = next(row for row in seed.places if row.id == "place-the-dubai-mall")
    effects = effects_on(seed.holidays, date(2026, 12, 2))
    assert effects is not None and effects.high_crowd
    assert places_for_day([mall], effects, avoid_crowds=True) == []
    culture = [
        row
        for row in seed.places
        if row.area == "Old Dubai"
        and row.operational_status == "open"
        and row.category not in {"mall", "beach"}
    ][:3]
    plan = sequence_itinerary(
        [mall, *culture],
        [row for row in seed.restaurants if row.area == "Old Dubai"],
        Constraints(days=1, start_date=date(2026, 12, 2), avoid_crowds=True, interests=["culture"]),
        holidays=seed.holidays,
        stations=seed.stations,
        edges=seed.edges,
        fares=seed.fares,
        stay=next(h for h in seed.hotels if h.area == "Old Dubai").stay_option("peak"),
        place_pool=culture,
    )
    ids = [slot.place_id for slot in plan.days[0].slots if slot.kind == "activity"]
    assert mall.id not in ids
    assert "National Day" in (plan.days[0].holiday_note or "")


def test_july_heat_inserts_a_rest_instead_of_midday_outdoor(seed) -> None:
    outdoor = [
        next(row for row in seed.places if row.id == "place-jbr-beach"),
        next(row for row in seed.places if row.id == "place-dubai-marina-promenade"),
        next(row for row in seed.places if row.id == "place-the-walk-at-jbr"),
    ]
    assert all(place.indoor is False for place in outdoor)
    july = next(row for row in seed.climate if row.month == 7)
    assert july.avg_high_c >= 35
    plan = sequence_itinerary(
        outdoor,
        [row for row in seed.restaurants if row.area == "Marina / JBR"],
        Constraints(days=1, start_date=date(2026, 7, 10), interests=["beach"]),
        climate=july,
        holidays=seed.holidays,
        stations=seed.stations,
        edges=seed.edges,
        fares=seed.fares,
        stay=next(h for h in seed.hotels if h.area == "Marina / JBR").stay_option("summer"),
    )
    rests = [slot for slot in plan.days[0].slots if slot.kind == "rest"]
    assert rests
    assert rests[0].start.hour <= 12
    assert rests[0].end.hour >= 16
    midday_outdoor = [
        slot
        for slot in plan.days[0].slots
        if slot.kind == "activity" and slot.start < time(16, 0) and slot.end > time(12, 0)
    ]
    assert midday_outdoor == []


def test_timed_entry_gets_a_note_not_a_ticket_hold(seed) -> None:
    timed = next(row for row in seed.places if row.timed_entry and row.operational_status == "open")
    plan = sequence_itinerary(
        [timed],
        [row for row in seed.restaurants if row.area == timed.area],
        Constraints(days=1, start_date=date(2026, 11, 18)),
        stations=seed.stations,
        edges=seed.edges,
        fares=seed.fares,
        stay=next(
            h for h in seed.hotels if h.area == timed.area or h.area == "Downtown"
        ).stay_option("peak"),
    )
    activity = next(slot for slot in plan.days[0].slots if slot.place_id == timed.id)
    assert activity.notes is not None
    assert "Timed entry" in activity.notes
