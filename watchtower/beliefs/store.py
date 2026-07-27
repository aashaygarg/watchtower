"""Persistence for beliefs, behind a storage-agnostic abstraction.

The belief engine depends on the :class:`BeliefStore` protocol, never on a
concrete backend. :class:`JsonBeliefStore` is the initial local implementation;
future ones may use SQLite or Postgres without changing any caller.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from watchtower.domain.beliefs import (
    Belief,
    BeliefAction,
    BeliefCategory,
    BeliefConfidence,
    BeliefStatus,
    BeliefUpdate,
)


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


class JsonBeliefStore:
    """A local JSON-backed belief store."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._beliefs: dict[str, Belief] = {}
        self._log: list[BeliefUpdate] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._path.is_file():
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._beliefs = {b["id"]: _belief_from_dict(b) for b in raw.get("beliefs", [])}
            self._log = [_update_from_dict(u) for u in raw.get("log", [])]
        self._loaded = True

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "beliefs": [_belief_to_dict(b) for b in self._beliefs.values()],
            "log": [_update_to_dict(u) for u in self._log],
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def all(self) -> tuple[Belief, ...]:
        self._ensure_loaded()
        return tuple(self._beliefs.values())

    def get(self, belief_id: str) -> Belief | None:
        self._ensure_loaded()
        return self._beliefs.get(belief_id)

    def upsert(self, belief: Belief) -> None:
        self._ensure_loaded()
        self._beliefs[belief.id] = belief
        self._flush()

    def record(self, update: BeliefUpdate) -> None:
        self._ensure_loaded()
        self._log.append(update)
        self._flush()

    def history(self) -> tuple[BeliefUpdate, ...]:
        self._ensure_loaded()
        return tuple(self._log)


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _parse_dt(value: Any) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _belief_to_dict(belief: Belief) -> dict[str, Any]:
    return {
        "id": belief.id,
        "title": belief.title,
        "description": belief.description,
        "category": belief.category.value,
        "confidence": belief.confidence.value,
        "supporting_evidence": list(belief.supporting_evidence),
        "contradicting_evidence": list(belief.contradicting_evidence),
        "assumptions": list(belief.assumptions),
        "status": belief.status.value,
        "created_at": _iso(belief.created_at),
        "updated_at": _iso(belief.updated_at),
        "revision": belief.revision,
        "superseded_by": belief.superseded_by,
    }


def _belief_from_dict(data: dict[str, Any]) -> Belief:
    return Belief(
        id=str(data["id"]),
        title=str(data.get("title", "")),
        description=str(data.get("description", "")),
        category=BeliefCategory(data.get("category", "strategy")),
        confidence=BeliefConfidence(data.get("confidence", "medium")),
        supporting_evidence=tuple(data.get("supporting_evidence", [])),
        contradicting_evidence=tuple(data.get("contradicting_evidence", [])),
        assumptions=tuple(data.get("assumptions", [])),
        status=BeliefStatus(data.get("status", "active")),
        created_at=_parse_dt(data.get("created_at")),
        updated_at=_parse_dt(data.get("updated_at")),
        revision=int(data.get("revision", 1)),
        superseded_by=data.get("superseded_by"),
    )


def _update_to_dict(update: BeliefUpdate) -> dict[str, Any]:
    return {
        "action": update.action.value,
        "rationale": update.rationale,
        "belief_id": update.belief_id,
        "title": update.title,
        "description": update.description,
        "category": update.category.value if update.category else None,
        "confidence": update.confidence.value if update.confidence else None,
        "evidence": list(update.evidence),
        "at": _iso(update.at),
    }


def _update_from_dict(data: dict[str, Any]) -> BeliefUpdate:
    category = data.get("category")
    confidence = data.get("confidence")
    return BeliefUpdate(
        action=BeliefAction(data.get("action", "no_change")),
        rationale=str(data.get("rationale", "")),
        belief_id=data.get("belief_id"),
        title=str(data.get("title", "")),
        description=str(data.get("description", "")),
        category=BeliefCategory(category) if category else None,
        confidence=BeliefConfidence(confidence) if confidence else None,
        evidence=tuple(data.get("evidence", [])),
        at=_parse_dt(data.get("at")),
    )
