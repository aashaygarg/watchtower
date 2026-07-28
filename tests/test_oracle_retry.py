"""Tests for oracle retry and the typed degraded judgment."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from watchtower.adapters.providers._retry import call_with_retry
from watchtower.domain.judgment import ThinkingResult, degraded_payload
from watchtower.domain.messages import Message, user
from watchtower.kernel.reasoning import think
from watchtower.startup.models import Startup, StartupId, StartupWorkspace


def test_call_with_retry_returns_first_success() -> None:
    attempts = {"n": 0}

    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("transient")
        return "ok"

    assert call_with_retry(flaky, attempts=3, default_factory=lambda: "default") == "ok"
    assert attempts["n"] == 2  # stopped as soon as it succeeded


def test_call_with_retry_returns_default_after_exhaustion() -> None:
    attempts = {"n": 0}

    def always_fail() -> str:
        attempts["n"] += 1
        raise RuntimeError("permanent")

    assert call_with_retry(always_fail, attempts=3, default_factory=lambda: "default") == "default"
    assert attempts["n"] == 3  # exactly `attempts` tries before the default


def test_call_with_retry_rejects_non_positive_attempts() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        call_with_retry(lambda: "x", attempts=0, default_factory=lambda: "y")


def test_degraded_payload_matches_degraded_judgment() -> None:
    payload = degraded_payload()
    degraded = ThinkingResult.degraded("Should we raise now?")
    assert payload["biggest_uncertainty"]  # explicit uncertainty, never empty
    assert degraded.recommendation == ""  # never a recommendation when degraded
    assert degraded.biggest_uncertainty == payload["biggest_uncertainty"]


class _FailingProvider:
    """A provider whose generation always fails; its complete_json must degrade."""

    def _generate(self, messages: Sequence[Message], *, as_json: bool) -> str:
        raise RuntimeError("provider down")

    def complete(self, messages: Sequence[Message]) -> str:  # pragma: no cover - unused here
        return self._generate(messages, as_json=False)

    def complete_json(self, messages: Sequence[Message]) -> dict[str, Any]:
        return call_with_retry(
            lambda: self._generate(messages, as_json=True),
            attempts=3,
            default_factory=degraded_payload,
        )


def _workspace() -> StartupWorkspace:
    return StartupWorkspace(
        root=Path("."),
        startup=Startup(id=StartupId("acme"), name="Acme"),
        vision="",
    )


def test_think_degrades_when_the_oracle_fails() -> None:
    result = think("Should we raise now?", workspace=_workspace(), llm=_FailingProvider())
    assert result == ThinkingResult.degraded("Should we raise now?")


def test_real_provider_complete_json_degrades_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from watchtower.adapters.providers.openai import OpenAICompatibleLLM

    llm = OpenAICompatibleLLM(model="test-model", api_key="dummy")

    def boom(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("api down")

    monkeypatch.setattr(llm, "_generate", boom)
    assert llm.complete_json([user("hi")]) == degraded_payload()
