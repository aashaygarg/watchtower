"""Base abstractions shared by all Watchtower agents."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Agent(Protocol):
    """Protocol implemented by every Watchtower agent."""

    name: str

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Advance the agent given the current graph ``state``."""
        ...
