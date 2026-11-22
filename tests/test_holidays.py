"""Holiday effects follow the trip date. They do not close the whole city."""

from datetime import date

from travel_planner.data.seed import load_seed
from travel_planner.models import DayPlan, Place, Restaurant
from travel_planner.rules import (
    apply_day_notes,
    effects_on,
    places_for_day,
    restaurants_for_day,
    trip_day_notes,
)


def _place(place_id: str, category: str, crowd: str = "low") -> Place:
    return Place(
        id=place_id,
        name=place_id,
        category=category,
        area="Downtown",
        lat=25.2,
        lng=55.27,
        crowd_level=crowd,  # type: ignore[arg-type]
        provenance="estimated",
        source="test",
        as_of=date(2026, 11, 18),
    )


def _restaurant(*meals: str) -> Restaurant:
    return Restaurant(
        id="restaurant-test",
        name="Test Kitchen",
        cuisine="unspecified",
        area="Downtown",
        lat=25.2,
        lng=55.27,
        price_band="mid",
        meal_types=list(meals),
        provenance="estimated",
        source="test",
        as_of=date(2026, 11, 18),
    )


def test_seed_calendar_covers_ramadan_eid_and_national_day() -> None:
    holidays = load_seed().holidays
    assert any(row.kind == "ramadan" and row.provenance == "estimated" for row in holidays)
    fitr = next(row for row in holidays if row.id == "eid-al-fitr-2026")
    assert fitr.provenance == "verified"
    assert fitr.start == date(2026, 3, 19)
    national = next(row for row in holidays if row.id == "national-day-2026")
    assert national.end == date(2026, 12, 3)


def test_eid_first_day_holds_heritage_and_marks_crowds() -> None:
    holidays = load_seed().holidays
    effects = effects_on(holidays, date(2026, 3, 19))
    assert effects is not None
    assert effects.heritage_may_close
    assert effects.high_crowd
    assert effects.drop_lunch
    museum = _place("place-museum", "museum")
    mall = _place("place-mall", "mall")
    beach = _place("place-beach", "beach", "medium")
    kept = places_for_day([museum, mall, beach], effects, avoid_crowds=False)
    assert [place.id for place in kept] == ["place-mall", "place-beach"]
    assert all(place.crowd_level == "high" for place in kept)
    assert places_for_day([mall, beach], effects, avoid_crowds=True) == []


def test_later_eid_day_keeps_museums() -> None:
    effects = effects_on(load_seed().holidays, date(2026, 3, 20))
    assert effects is not None
    assert effects.heritage_may_close is False
    assert effects.high_crowd
    museum = _place("place-museum", "museum")
    kept = places_for_day([museum], effects, avoid_crowds=False)
    assert kept == [museum]


def test_ramadan_drops_lunch_and_omits_a_lunch_only_restaurant() -> None:
    effects = effects_on(load_seed().holidays, date(2027, 2, 10))
    assert effects is not None
    assert effects.drop_lunch
    assert "estimated" in effects.note()
    both = restaurants_for_day([_restaurant("lunch", "dinner")], effects)
    assert both[0].meal_types == ["dinner"]
    assert restaurants_for_day([_restaurant("lunch")], effects) == []


def test_a_normal_day_leaves_places_and_meals_alone() -> None:
    holidays = load_seed().holidays
    assert effects_on(holidays, date(2026, 11, 18)) is None
    place = _place("place-beach", "beach")
    meal = _restaurant("lunch", "dinner")
    assert places_for_day([place], None, avoid_crowds=True) == [place]
    assert restaurants_for_day([meal], None) == [meal]


def test_trip_notes_name_the_holiday_on_the_overlapping_day() -> None:
    holidays = load_seed().holidays
    notes = trip_day_notes(holidays, date(2026, 12, 1), 3)
    assert notes[0].startswith("Day 2 (2026-12-02): UAE National Day")
    assert "crowded" in notes[0]
    assert notes[1].startswith("Day 3 (2026-12-03):")
    plans = apply_day_notes(
        [DayPlan(day=1, theme="creek"), DayPlan(day=2, theme="downtown")],
        holidays,
        date(2026, 12, 1),
    )
    assert plans[0].holiday_note is None
    assert plans[1].holiday_note is not None
    assert "National Day" in plans[1].holiday_note
    assert trip_day_notes(holidays, None, 4) == []
