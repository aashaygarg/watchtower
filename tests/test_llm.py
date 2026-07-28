"""Tests for provider-agnostic LLM selection.

These verify that provider selection comes entirely from configuration, without
requiring the optional provider SDKs to be installed. The cognition layer's
provider-agnosticism is covered separately in test_cognition.py (it drives a
fake LLM through the same protocol).
"""

from __future__ import annotations

import importlib.util

import pytest
from watchtower.adapters.providers import LLMUnavailableError, build_oracle
from watchtower.adapters.providers.openai import OpenAICompatibleLLM
from watchtower.config import LLMConfig


def test_default_provider_is_openai_compatible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    llm = build_oracle(LLMConfig())
    assert isinstance(llm, OpenAICompatibleLLM)


def test_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    with pytest.raises(LLMUnavailableError, match="unknown LLM provider"):
        build_oracle(LLMConfig(provider="does-not-exist"))


def test_anthropic_uses_provider_default_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Provider selection is config-driven; the key env defaults per provider.
    with pytest.raises(LLMUnavailableError, match=r"\$ANTHROPIC_API_KEY"):
        build_oracle(LLMConfig(provider="anthropic"))


def test_gemini_uses_provider_default_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(LLMUnavailableError, match=r"\$GEMINI_API_KEY"):
        build_oracle(LLMConfig(provider="gemini"))


def test_api_key_env_override_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CUSTOM_KEY", raising=False)
    with pytest.raises(LLMUnavailableError, match=r"\$CUSTOM_KEY"):
        build_oracle(LLMConfig(provider="anthropic", api_key_env="CUSTOM_KEY"))


def test_ollama_needs_no_key_but_needs_package() -> None:
    # Ollama requires no API key. Without the package installed, it should raise
    # a package error rather than a key error.
    if importlib.util.find_spec("ollama") is not None:
        pytest.skip("ollama is installed; skipping the missing-package path")
    with pytest.raises(LLMUnavailableError, match="ollama package"):
        build_oracle(LLMConfig(provider="ollama"))
