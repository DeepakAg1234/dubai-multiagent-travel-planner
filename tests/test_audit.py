"""Pasted-itinerary checks. No network and no LLM."""

from travel_planner.audit import EXAMPLE_TEXT, audit_itinerary
from travel_planner.data.seed import SeedBundle


def _audit(seed: SeedBundle, text: str):
    return audit_itinerary(
        text,
        places=seed.places,
        restaurants=seed.restaurants,
        hotels=seed.hotels,
        stations=seed.stations,
        edges=seed.edges,
        fares=seed.fares,
        bands=seed.price_bands,
        holidays=seed.holidays,
        climate=seed.climate,
    )


def test_example_catches_what_a_chatbot_misses(seed: SeedBundle) -> None:
    report = _audit(seed, EXAMPLE_TEXT)

    unknown = {name.casefold() for name in report.unknown}
    assert "dubai chocolate factory" in unknown
    assert "dubai crystal caves" in unknown
    assert any(row.code == "not_in_catalog" for row in report.findings)
    assert any(row.code == "operational_status" for row in report.findings)
    assert any(row.code == "budget_compliance" for row in report.findings)
    assert report.verdict == "still_blocked"
    assert report.original is not None
    assert report.original.budget is not None
    assert report.original.budget.total_aed > 900
    assert report.repaired is not None
    scheduled = {
        slot.place_id
        for day in report.repaired.days
        for slot in day.slots
        if slot.kind == "activity"
    }
    assert "place-museum-of-the-future" not in scheduled
    assert report.repairs
    assert report.headline


def test_real_places_can_be_rebuilt(seed: SeedBundle) -> None:
    text = """
    3-day trip. Budget AED 20000.

    Day 1
    Al Fahidi Historical Neighbourhood

    Day 2
    The Dubai Mall

    Day 3
    Kite Beach
    """
    report = _audit(seed, text)
    names = {row.name for row in report.recognized}
    assert "Al Fahidi Historical Neighbourhood" in names
    assert "The Dubai Mall" in names
    assert "Kite Beach" in names
    assert report.unknown == []
    assert report.repaired is not None
    assert report.verdict in {"clear", "repaired"}
    assert report.repaired.budget is not None
    assert report.repaired.budget.within_budget


def test_invented_places_are_not_replaced_with_a_new_trip(seed: SeedBundle) -> None:
    report = _audit(
        seed,
        "Day 1\nVisit the Dubai Chocolate Factory\nThen the Crystal Caves of Dubai\n",
    )
    assert report.recognized == []
    assert report.repaired is None
    assert report.verdict == "still_blocked"
    assert any(row.code == "not_in_catalog" for row in report.findings)
