"""Planning areas used by the curated dataset."""

PLANNING_AREAS: tuple[str, ...] = (
    "Old Dubai",
    "Downtown",
    "Marina / JBR",
    "Jumeirah",
    "Al Quoz",
    "Palm",
    "Dubai Creek",
    "Business Bay",
)

# Thin areas merge onto a neighbour on the same Metro line.
AREA_NEIGHBOUR: dict[str, str] = {
    "Business Bay": "Downtown",
    "Al Quoz": "Downtown",
    "Dubai Creek": "Old Dubai",
}


# Satellite places have no hotel or restaurant row. Stay and meals use a planning area.
SATELLITE_HOST: dict[str, str] = {
    "Dubailand": "Downtown",
    "Al Barsha": "Marina / JBR",
    "Zabeel": "Downtown",
    "Al Mamzar": "Dubai Creek",
    "Al Qudra": "Jumeirah",
    "Mushrif": "Downtown",
    "Jebel Ali": "Marina / JBR",
    "Dubai Hills": "Downtown",
    "Mirdif": "Downtown",
    "Meydan": "Downtown",
    "Expo": "Marina / JBR",
}


def neighbour_area(area: str) -> str:
    return AREA_NEIGHBOUR.get(area, area)


def stay_area(area: str) -> str:
    """Planning area that can host a hotel and meals for a place."""

    if area in PLANNING_AREAS:
        return area
    return SATELLITE_HOST.get(area, "Downtown")
