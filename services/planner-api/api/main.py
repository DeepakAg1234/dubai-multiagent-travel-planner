"""Planner API. Streams AgentEvent values and state slices as SSE.

Public ingress is ``/api/planner/*``. The service rewrite strips that prefix,
so these routes are ``/runs``, ``/graph``, and ``/health``.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

_SRC = Path(__file__).resolve().parents[3] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import Response, StreamingResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from travel_planner.audit import EXAMPLE_TEXT, AuditReport  # noqa: E402
from travel_planner.config import get_settings  # noqa: E402
from travel_planner.llm import provider_status  # noqa: E402
from travel_planner.present import itinerary_markdown, result_payload  # noqa: E402
from travel_planner.service import PlannerService  # noqa: E402

app = FastAPI(title="Dubai travel planner API", version="0.7.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
_service: PlannerService | None = None

_STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class PlanRequest(BaseModel):
    request: str = ""
    thread_id: str | None = None
    resume: str | None = None
    use_live_apis: bool | None = None


class AuditRequest(BaseModel):
    text: str = ""


def get_service() -> PlannerService:
    global _service
    if _service is None:
        try:
            _service = PlannerService(_settings_for_api())
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _service


def _settings_for_api():
    """Prefer the repo database, then a sqlite file bundled beside this service."""

    settings = get_settings()
    if settings.sqlite_path.is_file():
        return settings
    bundled = Path(__file__).resolve().parents[1] / "dubai.sqlite"
    if bundled.is_file():
        return settings.model_copy(update={"data_db_path": str(bundled)})
    return settings


@app.get("/health")
def health() -> dict[str, object]:
    settings = _settings_for_api()
    return {
        "status": "ok",
        "service": "planner-api",
        "database": settings.sqlite_path.is_file(),
        "env": {
            "ollama_configured": settings.ollama_enabled,
            "groq_configured": settings.groq_enabled,
            "anthropic_configured": settings.anthropic_enabled,
            "ors_configured": bool(settings.ors_api_key.strip()),
            "use_live_apis": settings.use_live_apis,
            "cache_store": settings.cache_enabled,
            "checkpoint_store": settings.checkpoint_enabled,
        },
    }


@app.get("/graph")
def graph() -> dict[str, str]:
    return {"mermaid": get_service().mermaid()}


@app.post("/runs")
def start_run(body: PlanRequest) -> StreamingResponse:
    thread_id = body.thread_id or str(uuid4())
    return _stream(body, thread_id, resume=body.resume)


@app.post("/runs/{run_id}/resume")
def resume_run(run_id: str, body: PlanRequest) -> StreamingResponse:
    if not (body.resume or "").strip():
        raise HTTPException(status_code=400, detail="A clarification answer is required.")
    return _stream(body, run_id, resume=body.resume)


@app.get("/audits/example")
def audit_example() -> dict[str, str]:
    return {"text": EXAMPLE_TEXT}


@app.post("/audits")
def audit(body: AuditRequest) -> AuditReport:
    text = body.text.strip()
    if len(text) < 20:
        raise HTTPException(status_code=400, detail="Paste an itinerary of at least a few lines.")
    if len(text) > 12_000:
        raise HTTPException(status_code=400, detail="That itinerary is too long to check.")
    return get_service().audit(text)


@app.post("/plan")
def plan(body: PlanRequest) -> StreamingResponse:
    """Earlier streaming path. Same events as ``POST /runs``."""

    return start_run(body)


@app.get("/runs/{run_id}/result")
def result(run_id: str, download: int = 0) -> Response:
    payload = _finished_payload(run_id)
    headers = {}
    if download:
        headers["Content-Disposition"] = 'attachment; filename="itinerary.json"'
    return Response(
        content=json.dumps(payload),
        media_type="application/json",
        headers=headers,
    )


@app.get("/runs/{run_id}/export.md")
def export_markdown(run_id: str) -> Response:
    payload = _finished_payload(run_id)
    body = itinerary_markdown(payload)
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="itinerary.md"'},
    )


def _finished_payload(run_id: str) -> dict[str, object]:
    service = get_service()
    try:
        snapshot = service.snapshot(run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Run not found.") from exc
    known = bool(
        snapshot.get("constraints")
        or snapshot.get("final")
        or snapshot.get("draft")
        or snapshot.get("assumptions")
        or snapshot.get("warnings")
    )
    if not known:
        raise HTTPException(status_code=404, detail="Run not found.")
    payload = result_payload(run_id, snapshot)
    if payload is None:
        raise HTTPException(status_code=409, detail="The run has not produced an itinerary yet.")
    return payload


def _stream(body: PlanRequest, thread_id: str, *, resume: str | None) -> StreamingResponse:
    service = get_service()

    def events() -> Iterator[str]:
        yield _sse(_meta(service, thread_id, body.use_live_apis), event="meta")
        checkpoints: list[dict[str, object]] = []

        def on_checkpoint(node: str, snapshot: dict[str, object]) -> None:
            checkpoints.append({"node": node, "snapshot": snapshot})

        try:
            for agent_event in service.run(
                body.request,
                thread_id=thread_id,
                resume=resume,
                use_live_apis=body.use_live_apis,
                on_checkpoint=on_checkpoint,
            ):
                yield from _flush(checkpoints)
                yield f"data: {agent_event.model_dump_json()}\n\n"
            yield from _flush(checkpoints)
        except Exception as exc:
            yield from _flush(checkpoints)
            yield _sse({"detail": str(exc)}, event="error")
            return
        pending = service.interrupts(thread_id)
        if pending:
            yield _sse({"thread_id": thread_id, "interrupts": pending}, event="interrupt")
            return
        values = service.values(thread_id)
        report = values.get("review_report")
        passed = bool(getattr(report, "passed", False))
        yield _sse({"thread_id": thread_id, "ok": True, "passed": passed}, event="done")

    return StreamingResponse(events(), media_type="text/event-stream", headers=_STREAM_HEADERS)


def _flush(checkpoints: list[dict[str, object]]) -> Iterator[str]:
    while checkpoints:
        yield _sse(checkpoints.pop(0), event="state")


def _meta(
    service: PlannerService,
    thread_id: str,
    requested_live: bool | None,
) -> dict[str, object]:
    settings = service.settings
    live = settings.use_live_apis if requested_live is None else requested_live
    status = provider_status(settings)
    return {
        "thread_id": thread_id,
        "live_apis": live,
        "api_call_budget": settings.api_call_budget,
        "durable_resume": settings.checkpoint_enabled,
        "llm": {
            "default_provider": status["default_provider"],
            "default_model": status["model"],
            "default_enabled": status["enabled"],
            "review_provider": status["review_provider"],
            "review_model": status["review_model"],
            "review_enabled": status["review_enabled"],
        },
    }


def _sse(payload: dict[str, object], *, event: str) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"
