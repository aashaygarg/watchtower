"""Interfaces for persisting and retrieving agent memory."""

from __future__ import annotations

from typing import Any, Protocol


class MemoryStore(Protocol):
    """Protocol for storing and retrieving agent memory."""

    def load(self, key: str) -> dict[str, Any] | None:
        """Return stored memory for ``key``, or ``None`` if absent."""
        ...

    def save(self, key: str, value: dict[str, Any]) -> None:
        """Persist ``value`` under ``key``."""
        ...
