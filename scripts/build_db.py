"""Validate the seed JSON and write data/dubai.sqlite."""

from travel_planner.config import REPO_ROOT, get_settings
from travel_planner.data.local import build_database
from travel_planner.data.seed import load_seed


def main() -> None:
    bundle = load_seed(REPO_ROOT / "data" / "seed")
    destination = get_settings().sqlite_path
    build_database(bundle, destination)
    print(
        "built",
        destination,
        f"places={len(bundle.places)}",
        f"restaurants={len(bundle.restaurants)}",
        f"hotels={len(bundle.hotels)}",
        f"stations={len(bundle.stations)}",
        f"edges={len(bundle.edges)}",
        f"holidays={len(bundle.holidays)}",
    )


if __name__ == "__main__":
    main()
