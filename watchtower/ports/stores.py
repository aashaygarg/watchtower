"""Storage ports: the persistence seams for beliefs and decisions.

The belief and decision engines depend only on these protocols, never on a
concrete backend. A JSON, SQLite, or Postgres adapter may implement them and is
wired in at the composition root without any change to the kernel.
"""

from __future__ import annotations

from typing import Protocol

from watchtower.domain.beliefs import Belief, BeliefUpdate
from watchtower.domain.decisions import Decision, DecisionEvent, DecisionReview


class BeliefStore(Protocol):
    """Storage-agnostic persistence for beliefs and their change log."""

    def all(self) -> tuple[Belief, ...]:
        """Return every belief, in any state."""
        ...

    def get(self, belief_id: str) -> Belief | None:
        """Return the belief with ``belief_id`` if it exists."""
        ...

    def upsert(self, belief: Belief) -> None:
        """Insert or replace ``belief`` by id."""
        ...

    def record(self, update: BeliefUpdate) -> None:
        """Append ``update`` to the append-only change log."""
        ...

    def history(self) -> tuple[BeliefUpdate, ...]:
        """Return the change log, oldest first."""
        ...


class DecisionStore(Protocol):
    """Storage-agnostic persistence for decisions, their history, and reviews."""

    def all(self) -> tuple[Decision, ...]:
        """Return every decision."""
        ...

    def get(self, decision_id: str) -> Decision | None:
        """Return the decision with ``decision_id`` if it exists."""
        ...

    def upsert(self, decision: Decision) -> None:
        """Insert or replace ``decision`` by id."""
        ...

    def record_event(self, event: DecisionEvent) -> None:
        """Append ``event`` to the append-only history."""
        ...

    def events(self) -> tuple[DecisionEvent, ...]:
        """Return the event history, oldest first."""
        ...

    def record_review(self, review: DecisionReview) -> None:
        """Persist a decision review."""
        ...

    def reviews(self) -> tuple[DecisionReview, ...]:
        """Return all reviews, oldest first."""
        ...
