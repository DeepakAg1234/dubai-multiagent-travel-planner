"""Distances used by fares and sequencing. Straight-line km is enough until Phase 5."""

from __future__ import annotations

import math
from typing import Protocol

EARTH_KM = 6371.0
WALK_KMH = 4.5
TAXI_KMH = 28.0


class HasCoords(Protocol):
    lat: float
    lng: float


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 2 * EARTH_KM * math.asin(min(1.0, math.sqrt(a)))


def distance_km(left: HasCoords, right: HasCoords) -> float:
    return haversine_km(left.lat, left.lng, right.lat, right.lng)


def minutes_at_speed(km: float, kmh: float) -> int:
    if kmh <= 0:
        return 0
    return max(1, round((km / kmh) * 60)) if km > 0 else 0


def walk_minutes(km: float) -> int:
    return minutes_at_speed(km, WALK_KMH)


def taxi_minutes(km: float) -> int:
    return minutes_at_speed(km, TAXI_KMH)


def nearest(target: HasCoords, candidates: list[HasCoords]) -> HasCoords | None:
    if not candidates:
        return None
    return min(candidates, key=lambda row: distance_km(target, row))
