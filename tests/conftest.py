"""Shared seed fixtures. Tests never call a network or an LLM."""

from __future__ import annotations

import pytest

from travel_planner.data.seed import SeedBundle, load_seed


@pytest.fixture(scope="session")
def seed() -> SeedBundle:
    return load_seed()
