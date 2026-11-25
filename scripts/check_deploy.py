"""Static checks for a Vercel preview of the fake-LLM planner.

Confirms the service shape, the read-only database build, and that the
example env file names every variable the API reads. It does not print
secret values and it does not call a provider.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_ENV = (
    "LLM_PROVIDER",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_MODEL",
    "ORS_API_KEY",
    "USE_LIVE_APIS",
    "MAX_REVISIONS",
    "BUFFER_PCT",
    "API_CALL_BUDGET",
    "CACHE_STORE_URL",
    "CHECKPOINT_STORE_URL",
)


def main() -> int:
    problems: list[str] = []
    vercel = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    services = vercel.get("services") or {}
    web = services.get("web") or {}
    api = services.get("planner-api") or {}
    if web.get("root") != "apps/web":
        problems.append("web service root must be apps/web")
    if api.get("framework") != "fastapi":
        problems.append("planner-api must be a FastAPI service")
    if "build_db.py" not in str(api.get("buildCommand")):
        problems.append("planner-api build must rebuild data/dubai.sqlite from seed")
    functions = api.get("functions") or {}
    duration = None
    for spec in functions.values():
        if isinstance(spec, dict):
            duration = spec.get("maxDuration")
    if duration != 300:
        problems.append("planner function maxDuration must be 300 seconds")
    rewrites = vercel.get("rewrites") or []
    planner = [
        row
        for row in rewrites
        if isinstance(row, dict) and str(row.get("source", "")).startswith("/api/planner")
    ]
    if not planner or planner[0].get("destination", {}).get("service") != "planner-api":
        problems.append("/api/planner must rewrite to the planner-api service")
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    for name in REQUIRED_ENV:
        if name not in example:
            problems.append(f".env.example is missing {name}")
    if "SARVAM_API_KEY" not in example:
        problems.append(".env.example is missing SARVAM_API_KEY")
    speech = ROOT / "apps" / "web" / "app" / "api" / "speech" / "route.ts"
    if not speech.is_file():
        problems.append("web speech route is missing")
    for row in rewrites:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source", ""))
        destination = row.get("destination")
        service = destination.get("service") if isinstance(destination, dict) else ""
        if source.startswith("/api/speech") and service == "planner-api":
            problems.append("/api/speech must stay on the web service")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    if "data/*.sqlite" not in gitignore:
        problems.append("generated sqlite must stay out of git")
    if ".env" not in gitignore:
        problems.append(".env must stay out of git")
    if problems:
        for line in problems:
            print(line)
        return 1
    print("deployment checks passed")
    print("preview: a missing ANTHROPIC_API_KEY keeps the stub agents")
    print("preview: USE_LIVE_APIS=false keeps routing and weather on the seed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
