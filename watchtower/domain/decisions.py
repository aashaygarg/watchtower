"""Decision domain model: what the founder actually chose to do.

Decisions are commitments the founder explicitly made, together with the
reasoning behind them and whether they turned out to be correct. They are
completely independent of beliefs: a decision may *link* the beliefs that
supported it (by id), but it never mutates a belief.

Like beliefs, decisions are pure, immutable, serializable data. Changes produce
new immutable values; history is preserved by the store's append-only event log
and stored reviews, never by silently overwriting prior reasoning.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class DecisionStatus(StrEnum):
    """Lifecycle state of a decision."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    REVIEWED = "reviewed"


class DecisionEventKind(StrEnum):
    """A kind of change recorded in a decision's append-only history."""

    CREATED = "created"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    REVIEWED = "reviewed"


@dataclass(frozen=True, slots=True, kw_only=True)
class Decision:
    """A commitment the founder explicitly made.

    Attributes:
        id: Stable unique identifier.
        title: A one-line statement of the decision.
        question: What was being decided.
        chosen_option: The option the founder chose.
        alternatives_considered: The options that were weighed and set aside.
        reasoning: Why the choice was made. Never overwritten once recorded.
        linked_beliefs: Ids of beliefs that supported the decision (references only).
        assumptions: What the decision took for granted.
        expected_outcomes: What the founder expected to happen.
        review_date: When the decision should be revisited, if set.
        status: Lifecycle state.
        created_at: When the decision was recorded.
        updated_at: When the decision last changed state.
        revision: How many times the decision has changed state (starts at 1).
    """

    id: str
    title: str
    question: str = ""
    chosen_option: str = ""
    alternatives_considered: tuple[str, ...] = ()
    reasoning: str = ""
    linked_beliefs: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    expected_outcomes: tuple[str, ...] = ()
    review_date: datetime | None = None
    status: DecisionStatus = DecisionStatus.PROPOSED
    created_at: datetime | None = None
    updated_at: datetime | None = None
    revision: int = 1


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionEvent:
    """One entry in a decision's append-only history.

    Attributes:
        decision_id: The decision the event belongs to.
        kind: What changed.
        note: A short human-readable note (e.g. a title or review summary).
        at: When the event occurred.
    """

    decision_id: str
    kind: DecisionEventKind
    note: str = ""
    at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionReview:
    """A structured, after-the-fact review of a decision.

    The purpose is to improve future judgment, not to judge the founder.

    Attributes:
        decision_id: The decision reviewed.
        verdict: A short, fair judgment of how the decision has held up.
        assumptions_that_held: Original assumptions that proved correct.
        assumptions_that_broke: Original assumptions that proved wrong.
        belief_changes: How the supporting beliefs have changed since.
        observed_evidence: The evidence observed since the decision.
        lessons: What to carry into future decisions.
        summary: A short prose summary.
        at: When the review was made.
    """

    decision_id: str
    verdict: str = ""
    assumptions_that_held: tuple[str, ...] = ()
    assumptions_that_broke: tuple[str, ...] = ()
    belief_changes: tuple[str, ...] = ()
    observed_evidence: tuple[str, ...] = ()
    lessons: tuple[str, ...] = ()
    summary: str = ""
    at: datetime | None = None
