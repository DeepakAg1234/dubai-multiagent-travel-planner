"""LLM provider factory.

Every LLM node, including review, uses Claude through the Anthropic API
(``claude-opus-5-5``). Ollama and Groq are not called. A missing
``ANTHROPIC_API_KEY`` disables the model and leaves the deterministic stubs
in place.
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

def provider_for_node(node: str, settings: Settings | None = None) -> str:
    """Every graph node uses Claude."""
    del node, settings
    return "anthropic"


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
    model = active.anthropic_model
    return {
        "default_provider": "anthropic",
        "review_provider": "anthropic",
        "review_model": model,
        "review_enabled": active.anthropic_enabled,
        "enabled": active.llm_enabled,
        "groq_enabled": False,
        "gemini_enabled": False,
        "ollama_enabled": False,
        "anthropic_enabled": active.anthropic_enabled,
        "groq_model": "",
        "ollama_model": "",
        "gemini_model": "",
        "anthropic_model": model,
        "model": model,
    }


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
    del temperature
    if provider != "anthropic":
        return None
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
