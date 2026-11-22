"""Apply the holiday calendar to a trip day.

Effects follow the holiday row, not a per-place closure list. Ramadan drops
lunch. The first day of an Eid window holds museums, mosques, and galleries
back. Eid and National Day raise crowds at malls, beaches, parks, and
viewpoints, and those places move off the day when the traveler asked to
avoid crowds. Every other place keeps its weekday hours.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from travel_planner.models import DayPlan, Holiday, Place, Restaurant

HERITAGE_CATEGORIES = frozenset({"museum", "mosque", "gallery"})
CROWD_CATEGORIES = frozenset(
    {"mall", "beach", "theme_park", "water_park", "viewpoint", "landmark", "park"}
)


@dataclass(frozen=True)
class DayEffects:
    """Holiday effects that apply to one calendar day."""

    day: date
    holidays: tuple[Holiday, ...]

    @property
    def drop_lunch(self) -> bool:
        return any("drop_lunch" in holiday.effects for holiday in self.holidays)

    @property
    def heritage_may_close(self) -> bool:
        return any(
            "heritage_may_close_first_day" in holiday.effects and holiday.start == self.day
            for holiday in self.holidays
        )

    @property
    def high_crowd(self) -> bool:
        return any("high_crowd" in holiday.effects for holiday in self.holidays)

    def note(self) -> str:
        labels = "; ".join(_label(holiday) for holiday in self.holidays)
        details: list[str] = []
        if self.drop_lunch:
            details.append(
                "Daytime dining is unreliable, so lunch is left off the plan "
                "and dinner hours are an estimate."
            )
        if self.heritage_may_close:
            details.append("Museums, mosques, and galleries may be closed; confirm before you go.")
        if self.high_crowd:
            details.append("Malls, beaches, theme parks, and viewpoints are likely crowded.")
        if not details:
            return labels + "."
        return labels + ". " + " ".join(details)


def effects_on(holidays: list[Holiday], day: date) -> DayEffects | None:
    matched = tuple(holiday for holiday in holidays if holiday.start <= day <= holiday.end)
    if not matched:
        return None
    return DayEffects(day, matched)


def trip_day_notes(holidays: list[Holiday], start: date | None, days: int) -> list[str]:
    """One note per trip day that overlaps the calendar. Empty when dates are unknown."""

    if start is None:
        return []
    notes: list[str] = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        effects = effects_on(holidays, day)
        if effects is not None:
            notes.append(f"Day {offset + 1} ({day.isoformat()}): {effects.note()}")
    return notes


def apply_day_notes(
    day_plans: list[DayPlan],
    holidays: list[Holiday],
    start: date | None,
) -> list[DayPlan]:
    """Copy day plans with `holiday_note` set from the calendar."""

    if start is None:
        return day_plans
    updated: list[DayPlan] = []
    for day_plan in day_plans:
        day = start + timedelta(days=day_plan.day - 1)
        effects = effects_on(holidays, day)
        note = effects.note() if effects is not None else None
        updated.append(day_plan.model_copy(update={"holiday_note": note}))
    return updated


def places_for_day(
    places: list[Place],
    effects: DayEffects | None,
    *,
    avoid_crowds: bool,
) -> list[Place]:
    """Places that can be scheduled on this day, with crowd levels adjusted."""

    if effects is None:
        return list(places)
    chosen: list[Place] = []
    for place in places:
        if effects.heritage_may_close and place.category in HERITAGE_CATEGORIES:
            continue
        if effects.high_crowd and place.category in CROWD_CATEGORIES:
            if avoid_crowds:
                continue
            if place.crowd_level != "high":
                place = place.model_copy(update={"crowd_level": "high"})
        chosen.append(place)
    return chosen


def restaurants_for_day(
    restaurants: list[Restaurant],
    effects: DayEffects | None,
) -> list[Restaurant]:
    """Drop lunch during Ramadan. A restaurant with no remaining meal is omitted."""

    if effects is None or not effects.drop_lunch:
        return list(restaurants)
    chosen: list[Restaurant] = []
    for restaurant in restaurants:
        meals = [meal for meal in restaurant.meal_types if meal != "lunch"]
        if not meals:
            continue
        if meals != restaurant.meal_types:
            restaurant = restaurant.model_copy(update={"meal_types": meals})
        chosen.append(restaurant)
    return chosen


def _label(holiday: Holiday) -> str:
    if holiday.provenance == "estimated":
        return f"{holiday.name} (dates estimated until the UAE moon-sighting announcement)"
    return holiday.name
