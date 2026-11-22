"""Repository interfaces. Agents depend on these, not on SQLite."""

from datetime import date
from typing import Protocol

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


class PlaceRepo(Protocol):
    def get(self, place_id: str) -> Place | None: ...

    def search(
        self,
        *,
        area: str | None = None,
        tag: str | None = None,
        status: str | None = None,
        category: str | None = None,
    ) -> list[Place]: ...


class RestaurantRepo(Protocol):
    def search(
        self,
        *,
        area: str | None = None,
        tier: str | None = None,
        cuisine: str | None = None,
    ) -> list[Restaurant]: ...


class HotelRepo(Protocol):
    def get(self, hotel_id: str) -> Hotel | None: ...

    def search(
        self,
        *,
        area: str | None = None,
        tier: str | None = None,
    ) -> list[Hotel]: ...


class TransitRepo(Protocol):
    def stations(self, *, line: str | None = None) -> list[TransitStation]: ...

    def edges(self, *, line: str | None = None) -> list[TransitEdge]: ...


class FareRepo(Protocol):
    def all(self) -> list[Fare]: ...

    def for_mode(self, mode: str) -> list[Fare]: ...


class PriceRepo(Protocol):
    def bands(
        self,
        *,
        category: str | None = None,
        tier: str | None = None,
    ) -> list[PriceBand]: ...


class ClimateRepo(Protocol):
    def month(self, month: int) -> ClimateMonth | None: ...

    def all(self) -> list[ClimateMonth]: ...


class HolidayRepo(Protocol):
    def all(self) -> list[Holiday]: ...

    def overlapping(self, start: date, end: date) -> list[Holiday]: ...
