"""Mistral provider routing and configuration tests without network calls."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.api.config import LLMProvider, Settings
from packages.ai import providers
from packages.ai.schemas import CriticAssessment


def test_mistral_is_a_supported_provider_and_integration() -> None:
    settings = Settings(_env_file=None, mistral_api_key="test-key")

    assert LLMProvider.MISTRAL.value == "mistral"
    assert settings.get_integration_status()["mistral"] == {
        "configured": True,
        "status": "configured",
    }


def test_mistral_requires_an_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        providers,
        "get_settings",
        lambda: SimpleNamespace(mistral_api_key=None),
    )

    with pytest.raises(ValueError, match="MISTRAL_API_KEY is not configured"):
        providers.get_mistral_model("mistral-large-latest")


def test_mistral_uses_openai_compatible_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        providers,
        "get_settings",
        lambda: SimpleNamespace(mistral_api_key="test-key"),
    )

    model = providers.get_mistral_model("mistral-large-latest", temperature=0.25)

    assert model.model_name == "mistral-large-latest"
    assert str(model.openai_api_base).rstrip("/") == "https://api.mistral.ai/v1"
    assert model.temperature == 0.25


def test_free_groq_llama_uses_supported_json_object_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeModel:
        def with_structured_output(self, schema, **kwargs):
            captured.update(schema=schema, **kwargs)
            return "structured"

    monkeypatch.setattr(providers, "get_llm", lambda *args, **kwargs: FakeModel())
    monkeypatch.setattr(
        providers,
        "get_settings",
        lambda: SimpleNamespace(
            critic_model_provider="groq",
            critic_model_name="llama-3.1-8b-instant",
        ),
    )

    result = providers.get_structured_llm(CriticAssessment, routing_type="critic")

    assert result == "structured"
    assert captured == {"schema": CriticAssessment, "method": "json_mode"}
