"""Tests for the event-sourced decision ledger: reconstruct state from the stream."""

from __future__ import annotations

from pathlib import Path

from watchtower.adapters.persistence import JsonDecisionStore
from watchtower.domain.decisions import (
    Decision,
    DecisionEventKind,
    DecisionReview,
    DecisionStatus,
)
from watchtower.kernel.ledger import mark_completed, record_decisions, record_review
from watchtower.kernel.ledger.events import (
    append_event,
    make_event,
    read_events,
    reconstruct,
    sequence_number,
)


def test_make_event_builds_a_decision_event() -> None:
    event = make_event("d1", DecisionEventKind.CREATED, note="Ship memory")
    assert event.decision_id == "d1"
    assert event.kind is DecisionEventKind.CREATED
    assert event.note == "Ship memory"


def test_append_event_is_immutable_and_ordered() -> None:
    base: tuple = ()
    first = make_event("d1", DecisionEventKind.CREATED)
    stream = append_event(base, first)
    assert stream == (first,)
    assert base == ()  # the original stream is never rewritten
    assert sequence_number(base) == 0
    assert sequence_number(stream) == 1


def test_read_events_filters_to_one_decision() -> None:
    events = (
        make_event("d1", DecisionEventKind.CREATED),
        make_event("d2", DecisionEventKind.CREATED),
        make_event("d1", DecisionEventKind.COMPLETED),
    )
    assert read_events(events, "d1") == (events[0], events[2])


def test_reconstruct_created_marks_accepted() -> None:
    events = (make_event("d1", DecisionEventKind.CREATED),)
    assert reconstruct(events) == {"d1": DecisionStatus.ACCEPTED}


def test_reconstruct_replays_the_full_lifecycle() -> None:
    events = (
        make_event("d1", DecisionEventKind.CREATED),
        make_event("d1", DecisionEventKind.COMPLETED),
        make_event("d1", DecisionEventKind.REVIEWED),
    )
    assert reconstruct(events) == {"d1": DecisionStatus.REVIEWED}


def test_reconstruct_tracks_decisions_independently() -> None:
    events = (
        make_event("d1", DecisionEventKind.CREATED),
        make_event("d2", DecisionEventKind.CREATED),
        make_event("d1", DecisionEventKind.COMPLETED),
    )
    assert reconstruct(events) == {
        "d1": DecisionStatus.COMPLETED,
        "d2": DecisionStatus.ACCEPTED,
    }


def test_decision_state_is_reconstructible_from_the_store_stream(tmp_path: Path) -> None:
    store = JsonDecisionStore(tmp_path / "decisions.json")
    record_decisions(
        store, [Decision(id="d1", title="Ship memory", status=DecisionStatus.ACCEPTED)]
    )
    assert reconstruct(store.events()) == {"d1": DecisionStatus.ACCEPTED}

    mark_completed(store, "d1")
    assert reconstruct(store.events()) == {"d1": DecisionStatus.COMPLETED}

    record_review(store, DecisionReview(decision_id="d1", summary="Paid off"))
    assert reconstruct(store.events()) == {"d1": DecisionStatus.REVIEWED}
