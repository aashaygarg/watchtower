"""Persistence for decisions, mirroring the belief store's architecture.

The decision engine depends on the :class:`DecisionStore` protocol, never on a
concrete backend. :class:`JsonDecisionStore` is the initial local implementation.
The store keeps current decisions, an append-only event log, and the reviews
made over time; prior reasoning is never overwritten.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from watchtower.decisions.models import (
    Decision,
    DecisionEvent,
    DecisionEventKind,
    DecisionReview,
    DecisionStatus,
)


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


class JsonDecisionStore:
    """A local JSON-backed decision store."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._decisions: dict[str, Decision] = {}
        self._events: list[DecisionEvent] = []
        self._reviews: list[DecisionReview] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._path.is_file():
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._decisions = {d["id"]: _decision_from_dict(d) for d in raw.get("decisions", [])}
            self._events = [_event_from_dict(e) for e in raw.get("events", [])]
            self._reviews = [_review_from_dict(r) for r in raw.get("reviews", [])]
        self._loaded = True

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "decisions": [_decision_to_dict(d) for d in self._decisions.values()],
            "events": [_event_to_dict(e) for e in self._events],
            "reviews": [_review_to_dict(r) for r in self._reviews],
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def all(self) -> tuple[Decision, ...]:
        self._ensure_loaded()
        return tuple(self._decisions.values())

    def get(self, decision_id: str) -> Decision | None:
        self._ensure_loaded()
        return self._decisions.get(decision_id)

    def upsert(self, decision: Decision) -> None:
        self._ensure_loaded()
        self._decisions[decision.id] = decision
        self._flush()

    def record_event(self, event: DecisionEvent) -> None:
        self._ensure_loaded()
        self._events.append(event)
        self._flush()

    def events(self) -> tuple[DecisionEvent, ...]:
        self._ensure_loaded()
        return tuple(self._events)

    def record_review(self, review: DecisionReview) -> None:
        self._ensure_loaded()
        self._reviews.append(review)
        self._flush()

    def reviews(self) -> tuple[DecisionReview, ...]:
        self._ensure_loaded()
        return tuple(self._reviews)


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _parse_dt(value: Any) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _decision_to_dict(decision: Decision) -> dict[str, Any]:
    return {
        "id": decision.id,
        "title": decision.title,
        "question": decision.question,
        "chosen_option": decision.chosen_option,
        "alternatives_considered": list(decision.alternatives_considered),
        "reasoning": decision.reasoning,
        "linked_beliefs": list(decision.linked_beliefs),
        "assumptions": list(decision.assumptions),
        "expected_outcomes": list(decision.expected_outcomes),
        "review_date": _iso(decision.review_date),
        "status": decision.status.value,
        "created_at": _iso(decision.created_at),
        "updated_at": _iso(decision.updated_at),
        "revision": decision.revision,
    }


def _decision_from_dict(data: dict[str, Any]) -> Decision:
    return Decision(
        id=str(data["id"]),
        title=str(data.get("title", "")),
        question=str(data.get("question", "")),
        chosen_option=str(data.get("chosen_option", "")),
        alternatives_considered=tuple(data.get("alternatives_considered", [])),
        reasoning=str(data.get("reasoning", "")),
        linked_beliefs=tuple(data.get("linked_beliefs", [])),
        assumptions=tuple(data.get("assumptions", [])),
        expected_outcomes=tuple(data.get("expected_outcomes", [])),
        review_date=_parse_dt(data.get("review_date")),
        status=DecisionStatus(data.get("status", "proposed")),
        created_at=_parse_dt(data.get("created_at")),
        updated_at=_parse_dt(data.get("updated_at")),
        revision=int(data.get("revision", 1)),
    )


def _event_to_dict(event: DecisionEvent) -> dict[str, Any]:
    return {
        "decision_id": event.decision_id,
        "kind": event.kind.value,
        "note": event.note,
        "at": _iso(event.at),
    }


def _event_from_dict(data: dict[str, Any]) -> DecisionEvent:
    return DecisionEvent(
        decision_id=str(data.get("decision_id", "")),
        kind=DecisionEventKind(data.get("kind", "created")),
        note=str(data.get("note", "")),
        at=_parse_dt(data.get("at")),
    )


def _review_to_dict(review: DecisionReview) -> dict[str, Any]:
    return {
        "decision_id": review.decision_id,
        "verdict": review.verdict,
        "assumptions_that_held": list(review.assumptions_that_held),
        "assumptions_that_broke": list(review.assumptions_that_broke),
        "belief_changes": list(review.belief_changes),
        "observed_evidence": list(review.observed_evidence),
        "lessons": list(review.lessons),
        "summary": review.summary,
        "at": _iso(review.at),
    }


def _review_from_dict(data: dict[str, Any]) -> DecisionReview:
    return DecisionReview(
        decision_id=str(data.get("decision_id", "")),
        verdict=str(data.get("verdict", "")),
        assumptions_that_held=tuple(data.get("assumptions_that_held", [])),
        assumptions_that_broke=tuple(data.get("assumptions_that_broke", [])),
        belief_changes=tuple(data.get("belief_changes", [])),
        observed_evidence=tuple(data.get("observed_evidence", [])),
        lessons=tuple(data.get("lessons", [])),
        summary=str(data.get("summary", "")),
        at=_parse_dt(data.get("at")),
    )
