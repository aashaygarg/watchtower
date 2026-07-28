"""Tests for the oracle call ceiling (runaway guard)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from watchtower.adapters.providers.limits import (
    CALL_LIMIT_ENV,
    LimitedOracle,
    OracleLimitExceededError,
    OracleStats,
    with_limits,
)
from watchtower.domain.messages import Message, user


class _CountingOracle:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages: Sequence[Message]) -> str:
        self.calls += 1
        return "ok"

    def complete_json(self, messages: Sequence[Message]) -> dict[str, Any]:
        self.calls += 1
        return {"ok": True}


def test_with_limits_is_a_noop_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(CALL_LIMIT_ENV, raising=False)
    oracle = _CountingOracle()
    assert with_limits(oracle) is oracle  # returned unwrapped: no behavior change


def test_with_limits_wraps_when_env_ceiling_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CALL_LIMIT_ENV, "5")
    wrapped = with_limits(_CountingOracle())
    assert isinstance(wrapped, LimitedOracle)


def test_invalid_env_ceiling_disables_the_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CALL_LIMIT_ENV, "not-a-number")
    oracle = _CountingOracle()
    assert with_limits(oracle) is oracle  # unparsable ceiling => no-op


def test_limited_oracle_raises_when_ceiling_exceeded() -> None:
    stats = OracleStats()
    oracle = LimitedOracle(_CountingOracle(), limit=2, stats=stats)

    assert oracle.complete_json([user("1")]) == {"ok": True}
    assert oracle.complete_json([user("2")]) == {"ok": True}
    with pytest.raises(OracleLimitExceededError):
        oracle.complete_json([user("3")])
    assert stats.calls == 3


def test_limited_oracle_counts_both_methods_and_resets() -> None:
    stats = OracleStats()
    oracle = LimitedOracle(_CountingOracle(), limit=10, stats=stats)

    oracle.complete([user("a")])
    oracle.complete_json([user("b")])
    assert stats.calls == 2

    stats.reset()
    assert stats.calls == 0
