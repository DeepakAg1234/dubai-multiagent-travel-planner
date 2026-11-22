"""Settings turn missing keys into disabled providers."""

from travel_planner.config import Settings
from travel_planner.llm import (
    chat_model_for,
    node_llm_enabled,
    provider_for_node,
    provider_status,
)

LLM_NODES = (
    "parse_request",
    "orchestrator_plan",
    "orchestrator_revise",
    "destination_research",
    "logistics_prelim",
    "logistics_sequence",
    "budget",
    "budget_adjust",
    "finalize",
    "review",
)


def test_missing_anthropic_key_disables_every_node() -> None:
    settings = Settings(
        _env_file=None,
        anthropic_api_key="",
        groq_api_key="groq-key",
        ollama_api_key="ollama-key",
        ollama_model="nemotron-3-nano",
    )
    assert settings.llm_enabled is False
    assert provider_status(settings)["enabled"] is False
    assert provider_status(settings)["groq_enabled"] is False
    assert provider_status(settings)["ollama_enabled"] is False
    for node in LLM_NODES:
        assert provider_for_node(node, settings) == "anthropic"
        assert node_llm_enabled(node, settings) is False
        assert chat_model_for(node, settings) is None


def test_gemini_api_key_falls_back_to_llm_api_key() -> None:
    settings = Settings(
        _env_file=None,
        gemini_api_key="",
        llm_api_key="legacy-gemini",
        gemini_model="",
        llm_model="gemini-flash",
    )
    assert settings.resolved_gemini_key == "legacy-gemini"
    assert settings.resolved_gemini_model == "gemini-flash"
    assert settings.gemini_enabled is True


def test_anthropic_provider_uses_claude_for_every_node() -> None:
    missing = Settings(_env_file=None, llm_provider="anthropic", anthropic_api_key="")
    assert missing.anthropic_enabled is False
    assert missing.llm_enabled is False
    assert provider_for_node("review", missing) == "anthropic"
    assert provider_for_node("parse_request", missing) == "anthropic"
    assert node_llm_enabled("review", missing) is False
    ready = Settings(
        _env_file=None,
        llm_provider="anthropic",
        anthropic_api_key="sk-ant-test",
        anthropic_model="claude-opus-5-5",
    )
    assert ready.llm_enabled is True
    assert node_llm_enabled("review", ready) is True
    assert node_llm_enabled("parse_request", ready) is True
    status = provider_status(ready)
    assert status["default_provider"] == "anthropic"
    assert status["model"] == "claude-opus-5-5"
    assert status["review_provider"] == "anthropic"
    assert status["review_model"] == "claude-opus-5-5"
    assert status["review_enabled"] is True
    assert status["anthropic_enabled"] is True


def test_anthropic_client_omits_sampling_parameters() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="anthropic",
        anthropic_api_key="sk-ant-test",
        anthropic_model="claude-opus-5-5",
    )
    model = chat_model_for("parse_request", settings, temperature=0.4)
    assert model is not None
    assert model.model == "claude-opus-5-5"
    assert model.temperature is None
    assert model.max_tokens == 16384
    payload = model._get_request_payload([("human", "hi")])
    assert payload["model"] == "claude-opus-5-5"
    assert payload["max_tokens"] == 16384
    assert "temperature" not in payload
    assert "top_p" not in payload
    assert "top_k" not in payload


def test_ors_stays_off_without_live_apis_or_a_key() -> None:
    with_key = Settings(_env_file=None, use_live_apis=False, ors_api_key="test-key")
    assert with_key.ors_enabled is False
    live_without_key = Settings(_env_file=None, use_live_apis=True, ors_api_key="")
    assert live_without_key.ors_enabled is False
    live = Settings(_env_file=None, use_live_apis=True, ors_api_key="test-key")
    assert live.ors_enabled is True


def test_empty_store_urls_disable_cache_and_checkpoints() -> None:
    settings = Settings(_env_file=None, cache_store_url="", checkpoint_store_url="")
    assert settings.cache_enabled is False
    assert settings.checkpoint_enabled is False
    assert settings.max_revisions == 3
    assert settings.buffer_pct == 10


def test_defaults_match_the_phase_0_decisions() -> None:
    settings = Settings(
        _env_file=None,
        use_live_apis=False,
        max_revisions=3,
        buffer_pct=10,
        api_call_budget=40,
    )
    assert settings.live_apis_enabled is False
    assert settings.api_call_budget == 40
    assert settings.llm_provider == "anthropic"
    assert settings.anthropic_model == "claude-opus-5-5"
    assert settings.llm_enabled is False
    status = provider_status(settings)
    assert status["default_provider"] == "anthropic"
    assert status["anthropic_model"] == "claude-opus-5-5"
    assert status["model"] == "claude-opus-5-5"
    assert status["review_provider"] == "anthropic"
    assert status["review_model"] == "claude-opus-5-5"
