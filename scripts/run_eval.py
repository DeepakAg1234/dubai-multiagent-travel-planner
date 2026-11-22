"""Score 10 offline requests and save the result for later comparison.

Usage:
    python scripts/run_eval.py

Writes evals/latest.json and evals/runs/<timestamp>.json. Exit code 1 when a
case misses the Phase 7 thresholds. Provider keys in the environment are
ignored so the run stays on the deterministic stubs.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from travel_planner.config import REPO_ROOT
from travel_planner.evalset import EVAL_CASES, offline_settings, score_run, threshold_failures
from travel_planner.service import PlannerService

RUNS = REPO_ROOT / "evals" / "runs"


def main() -> int:
    service = PlannerService(settings=offline_settings())
    places = {place.id: place for place in service.tools.places}
    holidays = service.tools.holidays
    scores = []
    for index, case in enumerate(EVAL_CASES):
        list(service.run(case.request, thread_id=f"eval-{index}", use_live_apis=False))
        scores.append(score_run(case, service.values(f"eval-{index}"), places, holidays))
    failures = threshold_failures(scores)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "offline": True,
        "cases": [score.as_dict() for score in scores],
        "failures": failures,
        "passed": not failures,
    }
    RUNS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    text = json.dumps(payload, indent=2)
    (RUNS / f"{stamp}.json").write_text(text, encoding="utf-8")
    (REPO_ROOT / "evals" / "latest.json").write_text(text, encoding="utf-8")
    for score in scores:
        flag = "ok" if score.budget_compliant or score.budget_flagged else "FAIL"
        print(
            f"{score.id:16} {flag:4} budget={score.total_aed} "
            f"coverage={score.interest_coverage} closed={score.closed_place_rate} "
            f"dup={score.duplicate_rate} holiday={score.holiday_adherence}"
        )
    if failures:
        print("thresholds failed:")
        for line in failures:
            print(f"- {line}")
        return 1
    print(f"wrote {RUNS / f'{stamp}.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
