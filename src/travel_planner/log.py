"""Logging that keeps keys and full prompts out of the default stream.

LangSmith tracing stays off unless ``LANGSMITH_TRACING`` is set. Traces that
do run receive a shortened node input: the raw request is a character count.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

_SECRET = re.compile(
    r"(?i)((?:ollama|groq|gemini|anthropic|ors|openai|langsmith|llm|api)[_-]?key|authorization)"
    r"(\s*[:=]\s*)(\S+)"
)
_BEARER = re.compile(r"(?i)Bearer\s+\S+")


def redact(text: str) -> str:
    """Replace key assignments and bearer tokens. The label stays so the leak is obvious."""

    cleaned = _BEARER.sub("Bearer [redacted]", text)
    return _SECRET.sub(lambda match: f"{match.group(1)}{match.group(2)}[redacted]", cleaned)


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("travel_planner")
    logger.setLevel(logging.INFO)
    if not any(isinstance(item, RedactFilter) for item in logger.filters):
        logger.addFilter(RedactFilter())
    return logger


def get_logger() -> logging.Logger:
    return configure_logging()


def tracing_requested() -> bool:
    return os.environ.get("LANGSMITH_TRACING", "").strip().lower() in {"1", "true", "yes"}


def trace_inputs(state: Any) -> Any:
    """Value recorded on a node trace. The request text is not included."""

    if not isinstance(state, dict):
        return {"omitted": True}
    raw = state.get("raw_request")
    summary: dict[str, object] = {
        "keys": sorted(str(key) for key in state),
        "revision_count": state.get("revision_count"),
    }
    if isinstance(raw, str):
        summary["request_chars"] = len(raw)
    constraints = state.get("constraints")
    days = getattr(constraints, "days", None)
    if days is not None:
        summary["days"] = days
    return summary


def trace_outputs(update: Any) -> Any:
    if not isinstance(update, dict):
        return {"omitted": True}
    return {"keys": sorted(str(key) for key in update if not str(key).startswith("_"))}
