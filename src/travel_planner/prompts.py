"""Load versioned prompt templates from ``prompts/``."""

from __future__ import annotations

from functools import lru_cache

from travel_planner.config import REPO_ROOT

PROMPTS_DIR = REPO_ROOT / "prompts"


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Return the shared grounding rules plus one node template."""

    grounding = (PROMPTS_DIR / "_grounding.v1.md").read_text(encoding="utf-8").strip()
    body = (PROMPTS_DIR / f"{name}.v1.md").read_text(encoding="utf-8").strip()
    return f"{grounding}\n\n{body}"
