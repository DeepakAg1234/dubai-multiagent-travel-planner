"""Free-API adapters. Each one fails soft so the catalog can take over."""

from travel_planner.data.providers.open_meteo import OpenMeteo
from travel_planner.data.providers.openrouteservice import OpenRouteService
from travel_planner.data.providers.osrm import Osrm
from travel_planner.data.providers.overpass import Overpass

__all__ = ["OpenMeteo", "OpenRouteService", "Osrm", "Overpass"]
