"""LLM provider factory.

Routing is node-based, not a single global model:

- ``LLM_PROVIDER=anthropic`` sends every LLM node, including review, to Claude.
- Otherwise ``review`` uses Groq (``openai/gpt-oss-20b``).
- Every other LLM node uses Ollama Cloud (``nemotron-3-nano``).
- ``LLM_PROVIDER=groq`` also sends those non-review nodes to Groq.

Phase 4 binds these clients to structured-output prompts. Missing keys disable
that provider instead of raising.
"""

from __future__ import annotations

from typing import Any

from travel_planner.config import Settings, get_settings

# Extraction, review, and budget narration stay at or below 0.2.
# Itinerary theming is allowed to sit a little higher.
NODE_TEMPERATURE: dict[str, float] = {
    "parse_request": 0.0,
    "review": 0.1,
    "budget": 0.1,
    "budget_adjust": 0.1,
    "finalize": 0.2,
    "orchestrator_plan": 0.4,
    "orchestrator_revise": 0.3,
    "destination_research": 0.2,
    "logistics_prelim": 0.2,
    "logistics_sequence": 0.4,
}

REVIEW_NODES = frozenset({"review"})
GROQ_NODES = frozenset(
    {
        "parse_request",
        "orchestrator_plan",
        "orchestrator_revise",
        "destination_research",
        "logistics_prelim",
        "logistics_sequence",
        "budget",
        "budget_adjust",
        "finalize",
    }
)


def provider_for_node(node: str, settings: Settings | None = None) -> str:
    """Return the configured provider name for a graph node."""
    active = settings or get_settings()
    provider = active.llm_provider.strip().lower()
    if provider == "anthropic":
        return "anthropic"
    if node in REVIEW_NODES or provider == "groq":
        return "groq"
    return "ollama"


def provider_enabled(provider: str, settings: Settings | None = None) -> bool:
    active = settings or get_settings()
    name = provider.strip().lower()
    if name == "gemini":
        return active.gemini_enabled
    if name == "groq":
        return active.groq_enabled
    if name == "ollama":
        return active.ollama_enabled
    if name == "anthropic":
        return active.anthropic_enabled
    return False


def node_llm_enabled(node: str, settings: Settings | None = None) -> bool:
    return provider_enabled(provider_for_node(node, settings), settings)


def provider_status(settings: Settings | None = None) -> dict[str, object]:
    active = settings or get_settings()
    provider = active.llm_provider.strip().lower()
    if provider == "anthropic":
        default = "anthropic"
        model = active.anthropic_model
    elif provider == "groq":
        default = "groq"
        model = active.groq_model
    else:
        default = "ollama"
        model = active.ollama_model
    review = provider_for_node("review", active)
    return {
        "default_provider": default,
        "review_provider": review,
        "review_model": _model_name(review, active),
        "review_enabled": provider_enabled(review, active),
        "enabled": active.llm_enabled,
        "groq_enabled": active.groq_enabled,
        "gemini_enabled": active.gemini_enabled,
        "ollama_enabled": active.ollama_enabled,
        "anthropic_enabled": active.anthropic_enabled,
        "groq_model": active.groq_model,
        "ollama_model": active.ollama_model,
        "gemini_model": active.resolved_gemini_model,
        "anthropic_model": active.anthropic_model,
        "model": model or active.resolved_gemini_model,
    }


def _model_name(provider: str, active: Settings) -> str:
    if provider == "anthropic":
        return active.anthropic_model
    if provider == "groq":
        return active.groq_model
    if provider == "gemini":
        return active.resolved_gemini_model
    return active.ollama_model


def chat_model_for(
    node: str,
    settings: Settings | None = None,
    *,
    temperature: float = 0.0,
) -> Any | None:
    """Build a LangChain chat model for ``node``, or ``None`` if that provider is off."""
    active = settings or get_settings()
    provider = provider_for_node(node, active)
    if not provider_enabled(provider, active):
        return None
    try:
        return _chat_model(provider, active, temperature)
    except ImportError:
        return None


def _chat_model(provider: str, active: Settings, temperature: float) -> Any | None:
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = active.resolved_gemini_model
        if not model:
            return None
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=active.resolved_gemini_key,
            temperature=temperature,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        model = active.anthropic_model.strip()
        api_key = active.anthropic_api_key.strip()
        if not model or not api_key:
            return None
        # Opus 5.5 rejects temperature, top_p, and top_k. Leave them unset.
        return ChatAnthropic(
            model=model,
            api_key=api_key,
            max_tokens=16384,
        )

    if provider == "groq":
        from langchain_groq import ChatGroq

        model = active.groq_model.strip()
        if not model:
            return None
        return ChatGroq(
            model=model,
            api_key=active.groq_api_key,
            temperature=temperature,
        )

    from langchain_ollama import ChatOllama

    model = active.ollama_model.strip()
    if not model:
        return None
    client_kwargs: dict[str, Any] = {}
    api_key = active.ollama_api_key.strip()
    if api_key:
        client_kwargs["headers"] = {"Authorization": f"Bearer {api_key}"}
    return ChatOllama(
        model=model,
        base_url=active.ollama_base_url,
        temperature=temperature,
        client_kwargs=client_kwargs,
    )
