"""Composition root: wire concrete adapters to the ports the app consumes.

This is the only module that constructs concrete adapters. The CLI and the kernel
depend on ports and receive their dependencies from here, so swapping an adapter
never touches anything above this seam.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from watchtower.adapters.persistence import JsonBeliefStore, JsonDecisionStore
from watchtower.adapters.providers import LLMUnavailableError, build_oracle
from watchtower.config import load_config
from watchtower.ports.oracle import Oracle
from watchtower.ports.stores import BeliefStore, DecisionStore

__all__ = ["AppContext", "LLMUnavailableError", "build_context", "build_oracle_for"]


@dataclass(frozen=True, slots=True)
class AppContext:
    """The persistence adapters the CLI always needs, behind their ports."""

    belief_store: BeliefStore
    decision_store: DecisionStore


def build_context(path: Path) -> AppContext:
    """Wire the local JSON stores for the workspace at ``path``."""
    watchtower_dir = path / ".watchtower"
    return AppContext(
        belief_store=JsonBeliefStore(watchtower_dir / "beliefs.json"),
        decision_store=JsonDecisionStore(watchtower_dir / "decisions.json"),
    )


def build_oracle_for(path: Path) -> Oracle:
    """Build the configured oracle for the workspace at ``path``.

    Raises:
        LLMUnavailableError: when no oracle can be constructed.
    """
    return build_oracle(load_config(search_from=path).llm)
