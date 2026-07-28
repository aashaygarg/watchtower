"""Event-sourced decision state: reconstruct decisions from their event stream.

A decision's life is an append-only stream of :class:`DecisionEvent`s - created,
completed, reviewed. Given the ordered stream, a decision's current lifecycle
status is a pure fold over its events: no stored status is needed to know where a
decision stands. This mirrors an event log - append events, never rewrite them,
and derive state by replay.

In Watchtower a decision is only ever recorded once the founder has committed to
it, so a ``CREATED`` event marks the decision ``ACCEPTED``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from watchtower.domain.decisions import DecisionEvent, DecisionEventKind, DecisionStatus

#: How each event kind sets a decision's lifecycle status when the stream is replayed.
_KIND_TO_STATUS = {
    DecisionEventKind.CREATED: DecisionStatus.ACCEPTED,
    DecisionEventKind.ACCEPTED: DecisionStatus.ACCEPTED,
    DecisionEventKind.REJECTED: DecisionStatus.REJECTED,
    DecisionEventKind.COMPLETED: DecisionStatus.COMPLETED,
    DecisionEventKind.REVIEWED: DecisionStatus.REVIEWED,
}


def make_event(
    decision_id: str,
    kind: DecisionEventKind,
    *,
    note: str = "",
    at: datetime | None = None,
) -> DecisionEvent:
    """Build a single decision event; its position in the stream is its sequence number."""
    return DecisionEvent(decision_id=decision_id, kind=kind, note=note, at=at)


def append_event(
    events: Sequence[DecisionEvent], event: DecisionEvent
) -> tuple[DecisionEvent, ...]:
    """Return a new stream with ``event`` appended. The existing stream is never rewritten."""
    return (*events, event)


def sequence_number(events: Sequence[DecisionEvent]) -> int:
    """Return the sequence number the next appended event would take (0-based)."""
    return len(events)


def read_events(events: Sequence[DecisionEvent], decision_id: str) -> tuple[DecisionEvent, ...]:
    """Return only the events belonging to ``decision_id``, in stream order."""
    return tuple(event for event in events if event.decision_id == decision_id)


def reconstruct(events: Sequence[DecisionEvent]) -> dict[str, DecisionStatus]:
    """Replay the stream into the current lifecycle status of every decision.

    Events are applied in order; the last event touching a decision determines its
    status. Decision state is therefore reconstructible purely from the stream.
    """
    status: dict[str, DecisionStatus] = {}
    for event in events:
        mapped = _KIND_TO_STATUS.get(event.kind)
        if mapped is not None:
            status[event.decision_id] = mapped
    return status
