"""A process-wide ceiling on oracle usage: a runaway guard, not billing.

Every oracle call is counted. An optional per-process ceiling caps how many calls
a single run may make, raising when it is exceeded - protection against an
accidental infinite reasoning loop. The guard is disabled (a pure no-op) when no
ceiling is configured, so ordinary runs are unaffected.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Sequence
from typing import Any

from watchtower.domain.messages import Message
from watchtower.ports.oracle import Oracle

#: Environment variable naming the per-process oracle call ceiling.
CALL_LIMIT_ENV = "WATCHTOWER_MAX_ORACLE_CALLS"


class OracleLimitExceededError(RuntimeError):
    """Raised when the configured oracle call ceiling is exceeded."""


class OracleStats:
    """A thread-safe, process-wide count of oracle calls."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls = 0

    @property
    def calls(self) -> int:
        """The number of oracle calls counted so far."""
        return self._calls

    def reset(self) -> None:
        """Reset the call count to zero."""
        with self._lock:
            self._calls = 0

    def record(self, *, limit: int | None) -> int:
        """Count one call, enforce ``limit``, and return the new call count.

        Raises:
            OracleLimitExceededError: When ``limit`` is set and now exceeded.
        """
        with self._lock:
            self._calls += 1
            if limit is not None and self._calls > limit:
                raise OracleLimitExceededError(
                    f"oracle call ceiling of {limit} exceeded (set ${CALL_LIMIT_ENV} to change it)"
                )
            return self._calls


#: The process-wide oracle call statistics.
STATS = OracleStats()


class LimitedOracle:
    """An oracle decorator that counts every call against a ceiling."""

    def __init__(self, inner: Oracle, *, limit: int, stats: OracleStats = STATS) -> None:
        self._inner = inner
        self._limit = limit
        self._stats = stats

    def complete(self, messages: Sequence[Message]) -> str:
        self._stats.record(limit=self._limit)
        return self._inner.complete(messages)

    def complete_json(self, messages: Sequence[Message]) -> dict[str, Any]:
        self._stats.record(limit=self._limit)
        return self._inner.complete_json(messages)


def with_limits(oracle: Oracle, *, limit: int | None = None) -> Oracle:
    """Wrap ``oracle`` with a call ceiling, or return it unchanged when disabled.

    The ceiling defaults to the ``WATCHTOWER_MAX_ORACLE_CALLS`` environment
    variable. When neither an explicit ``limit`` nor the variable is set, the
    oracle is returned unwrapped - the guard is a pure no-op.
    """
    resolved = limit if limit is not None else _read_limit()
    if resolved is None:
        return oracle
    return LimitedOracle(oracle, limit=resolved)


def _read_limit() -> int | None:
    raw = os.getenv(CALL_LIMIT_ENV)
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None
