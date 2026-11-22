"""Planner API contract: SSE, resume, and on-demand exports. Agents are stubs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from travel_planner.config import Settings
from travel_planner.service import PlannerService

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "planner-api"))

from api import main as api_main  # noqa: E402

PASS = "2 days culture beaches AED 5000 start:2026-11-18"


@pytest.fixture
def client():
    """One in-memory planner with provider keys forced off."""

    settings = Settings(
        llm_provider="ollama",
        ollama_api_key="",
        groq_api_key="",
        anthropic_api_key="",
        gemini_api_key="",
        llm_api_key="",
        use_live_apis=False,
    )
    api_main._service = PlannerService(settings)
    with TestClient(api_main.app) as test_client:
        yield test_client
    api_main._service = None


def test_health_and_graph(client: TestClient):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["database"] is True
    diagram = client.get("/graph")
    assert diagram.status_code == 200
    assert "parse_request" in diagram.json()["mermaid"]
    assert "budget_adjust" in diagram.json()["mermaid"]


def test_run_streams_state_revision_and_export(client: TestClient):
    with client.stream(
        "POST",
        "/runs",
        json={"request": "force:budget", "use_live_apis": False},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    events = _parse_sse(body)
    names = [name for name, _ in events]
    assert "meta" in names
    assert "state" in names
    assert "done" in names
    nodes = [payload.get("node") for name, payload in events if name == "message"]
    assert "parse_request" in nodes
    assert "budget_adjust" in nodes
    assert any(payload.get("phase") == "revision" for name, payload in events if name == "message")
    state = next(payload for name, payload in events if name == "state")
    assert "revision_count" in state["snapshot"]
    assert "constraints" in state["snapshot"]
    thread_id = next(payload["thread_id"] for name, payload in events if name == "meta")
    result = client.get(f"/runs/{thread_id}/result")
    assert result.status_code == 200
    payload = result.json()
    assert payload["itinerary"]["days"]
    assert payload["itinerary"]["budget"]["total_aed"] >= 0
    exported = client.get(f"/runs/{thread_id}/export.md")
    assert exported.status_code == 200
    assert "text/markdown" in exported.headers["content-type"]
    text = exported.text
    assert "Day 1" in text
    assert "AED" in text
    assert "estimated" in text
    assert not (ROOT / "itinerary.md").exists()
    assert not (ROOT / "itinerary.json").exists()


def test_interrupt_then_resume(client: TestClient):
    with client.stream(
        "POST",
        "/runs",
        json={"request": "a weekend somewhere", "use_live_apis": False},
    ) as response:
        body = "".join(response.iter_text())
    events = _parse_sse(body)
    assert any(name == "interrupt" for name, _ in events)
    thread_id = next(payload["thread_id"] for name, payload in events if name == "meta")
    missing = client.get(f"/runs/{thread_id}/export.md")
    assert missing.status_code == 409
    with client.stream(
        "POST",
        f"/runs/{thread_id}/resume",
        json={"resume": PASS, "use_live_apis": False},
    ) as response:
        resumed = "".join(response.iter_text())
    done = _parse_sse(resumed)
    assert any(name == "done" and payload.get("passed") is True for name, payload in done)
    saved = client.get(f"/runs/{thread_id}/result?download=1")
    assert saved.status_code == 200
    assert "attachment" in saved.headers["content-disposition"]


def test_unknown_run_is_missing(client: TestClient):
    missing = client.get("/runs/does-not-exist/result")
    assert missing.status_code == 404


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    parsed: list[tuple[str, dict]] = []
    for chunk in body.split("\n\n"):
        if not chunk.strip():
            continue
        event = "message"
        data: list[str] = []
        for line in chunk.splitlines():
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data.append(line.split(":", 1)[1].strip())
        if data:
            parsed.append((event, json.loads("\n".join(data))))
    return parsed
