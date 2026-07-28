"""The session fold: compile a finished conversation into durable state.

Every conversation becomes evidence. The fold runs one worldview-update pass and
one decision-capture pass over the transcript, applying belief updates and
recording only the decisions the founder explicitly committed to. It takes ports
and returns what changed, leaving presentation to the caller; the transcript
itself is discarded.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from watchtower.domain.beliefs import BeliefUpdate
from watchtower.domain.decisions import Decision
from watchtower.kernel.ledger import capture_decisions, record_decisions
from watchtower.kernel.worldview import apply_updates, update_beliefs
from watchtower.ports.oracle import Oracle
from watchtower.ports.stores import BeliefStore, DecisionStore


@dataclass(frozen=True, slots=True)
class FoldResult:
    """What a fold changed: applied belief updates and captured decisions."""

    belief_updates: tuple[BeliefUpdate, ...]
    captured_decisions: tuple[Decision, ...]


def fold(
    *,
    history: Sequence[str],
    belief_store: BeliefStore,
    decision_store: DecisionStore,
    oracle: Oracle,
) -> FoldResult:
    """Compile ``history`` into worldview updates and captured decisions.

    Updates the worldview from the conversation and records only the decisions
    the founder explicitly committed to. Returns what changed, for rendering.
    """
    applied = apply_updates(belief_store, update_beliefs(history, belief_store.all(), oracle))
    captured = capture_decisions(history, belief_store.all(), oracle)
    if captured:
        record_decisions(decision_store, captured)
    return FoldResult(belief_updates=applied, captured_decisions=captured)
