"""Structured LLM calls: schema check, one repair, then a node fallback.

A missing provider key does not call a model. The node keeps its deterministic
stub. Rate-limit errors retry with backoff before that repair step.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock

from pydantic import BaseModel, ValidationError

from travel_planner.config import Settings
from travel_planner.llm import NODE_TEMPERATURE, chat_model_for, node_llm_enabled
from travel_planner.prompts import load_prompt

ChatFn = Callable[[list[tuple[str, str]]], object]
Sleeper = Callable[[float], None]

_RATE_LIMIT_ATTEMPTS = 4
_BACKOFF_SECONDS = 0.5


@dataclass
class NodeUsage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    repairs: int = 0
    fallbacks: int = 0


@dataclass
class UsageLedger:
    """Per-node call and token counts for one planner run."""

    _lock: Lock = field(default_factory=Lock)
    nodes: dict[str, NodeUsage] = field(default_factory=dict)

    def add(
        self,
        node: str,
        *,
        calls: int,
        prompt_tokens: int,
        completion_tokens: int,
        repairs: int,
        fallback: bool,
    ) -> None:
        with self._lock:
            row = self.nodes.setdefault(node, NodeUsage())
            row.calls += calls
            row.prompt_tokens += prompt_tokens
            row.completion_tokens += completion_tokens
            row.repairs += repairs
            if fallback:
                row.fallbacks += 1

    def snapshot(self) -> dict[str, dict[str, int]]:
        with self._lock:
            return {
                name: {
                    "calls": row.calls,
                    "prompt_tokens": row.prompt_tokens,
                    "completion_tokens": row.completion_tokens,
                    "repairs": row.repairs,
                    "fallbacks": row.fallbacks,
                }
                for name, row in self.nodes.items()
            }


@dataclass(frozen=True)
class LlmOutcome[T]:
    value: T
    used_fallback: bool
    repaired: bool
    calls: int
    prompt_tokens: int
    completion_tokens: int

    def tokens(self) -> dict[str, int] | None:
        if self.calls == 0 and self.prompt_tokens == 0 and self.completion_tokens == 0:
            return None
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
        }


def bind_chat(node: str, settings: Settings, chat: ChatFn | None) -> ChatFn | None:
    """Use an injected chat function, otherwise the provider for ``node``."""

    if chat is not None:
        return chat
    if not node_llm_enabled(node, settings):
        return None
    model = chat_model_for(node, settings, temperature=NODE_TEMPERATURE.get(node, 0.2))
    if model is None:
        return None

    def _call(messages: list[tuple[str, str]]) -> object:
        return model.invoke(list(messages))

    return _call


def complete[T: BaseModel](
    node: str,
    schema: type[T],
    data: str,
    *,
    settings: Settings,
    fallback: Callable[[], T],
    chat: ChatFn | None = None,
    ledger: UsageLedger | None = None,
    check: Callable[[T], str | None] | None = None,
    sleeper: Sleeper | None = None,
) -> LlmOutcome[T]:
    """Validate model JSON, repair once, then call ``fallback``."""

    bound = bind_chat(node, settings, chat)
    if bound is None:
        value = fallback()
        _record(
            ledger,
            node,
            calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            repairs=0,
            fallback=True,
        )
        return LlmOutcome(value, True, False, 0, 0, 0)

    system = load_prompt(node)
    user = f"DATA\n{data}"
    messages: list[tuple[str, str]] = [("system", system), ("human", user)]
    sleep = sleeper or time.sleep
    calls = 0
    prompt_tokens = 0
    completion_tokens = 0
    repaired = False
    last_error = "The model returned no JSON object."

    for attempt in range(2):
        try:
            response = _invoke_with_backoff(bound, messages, sleep)
        except Exception as exc:
            last_error = str(exc)
            break
        calls += 1
        prompt_delta, completion_delta = _usage(response)
        prompt_tokens += prompt_delta
        completion_tokens += completion_delta
        try:
            parsed = schema.model_validate(_extract_json(_message_text(response)))
            if check is not None:
                problem = check(parsed)
                if problem:
                    raise ValueError(problem)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            if attempt == 0:
                repaired = True
                messages = [
                    *messages,
                    (
                        "human",
                        "The previous output failed validation: "
                        f"{last_error}. Reply with one JSON object only.",
                    ),
                ]
                continue
            break
        _record(
            ledger,
            node,
            calls=calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            repairs=1 if repaired else 0,
            fallback=False,
        )
        return LlmOutcome(parsed, False, repaired, calls, prompt_tokens, completion_tokens)

    value = fallback()
    _record(
        ledger,
        node,
        calls=calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        repairs=1 if repaired else 0,
        fallback=True,
    )
    _ = last_error
    return LlmOutcome(value, True, repaired, calls, prompt_tokens, completion_tokens)


def _record(ledger: UsageLedger | None, node: str, **kwargs: object) -> None:
    if ledger is None:
        return
    ledger.add(
        node,
        calls=int(kwargs["calls"]),  # type: ignore[arg-type]
        prompt_tokens=int(kwargs["prompt_tokens"]),  # type: ignore[arg-type]
        completion_tokens=int(kwargs["completion_tokens"]),  # type: ignore[arg-type]
        repairs=int(kwargs["repairs"]),  # type: ignore[arg-type]
        fallback=bool(kwargs["fallback"]),
    )


def _invoke_with_backoff(
    chat: ChatFn,
    messages: list[tuple[str, str]],
    sleeper: Sleeper,
) -> object:
    delay = _BACKOFF_SECONDS
    last: Exception | None = None
    for attempt in range(_RATE_LIMIT_ATTEMPTS):
        try:
            return chat(messages)
        except Exception as exc:
            last = exc
            if not _is_rate_limit(exc) or attempt == _RATE_LIMIT_ATTEMPTS - 1:
                raise
            sleeper(delay)
            delay *= 2
    raise RuntimeError("LLM call failed") from last


def _is_rate_limit(exc: Exception) -> bool:
    text = str(exc).lower()
    return "429" in text or "rate limit" in text or "too many requests" in text


def _message_text(response: object) -> str:
    if isinstance(response, str):
        return response
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
            else:
                text = getattr(block, "text", None)
                if isinstance(text, str) and text:
                    parts.append(text)
        return "\n".join(parts)
    if isinstance(response, dict) and "content" in response:
        return str(response["content"])
    return str(response)


def _usage(response: object) -> tuple[int, int]:
    raw = getattr(response, "usage_metadata", None)
    if raw is None and isinstance(response, dict):
        raw = response.get("usage_metadata") or response.get("usage")
    if raw is None:
        return (0, 0)
    if not isinstance(raw, dict):
        raw = {
            "input_tokens": getattr(raw, "input_tokens", 0),
            "output_tokens": getattr(raw, "output_tokens", 0),
        }
    prompt = raw.get("input_tokens") or raw.get("prompt_tokens") or 0
    completion = raw.get("output_tokens") or raw.get("completion_tokens") or 0
    return (int(prompt), int(completion))


def _extract_json(text: str) -> object:
    body = text.strip()
    if body.startswith("```"):
        lines = [line for line in body.splitlines() if not line.strip().startswith("```")]
        body = "\n".join(lines).strip()
    start = body.find("{")
    end = body.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in the model output")
    return json.loads(body[start : end + 1])
