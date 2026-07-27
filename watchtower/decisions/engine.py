"""The decision engine: explicit capture, completion, and review.

No embeddings, retrieval, or agents. Decisions are captured only when the
founder explicitly commits to an action - never inferred from a recommendation.
Beliefs are read (to link and to review), but this module never mutates them, so
the Belief Engine is untouched.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import uuid4

from watchtower.decisions.store import DecisionStore
from watchtower.domain.beliefs import Belief
from watchtower.domain.decisions import (
    Decision,
    DecisionEvent,
    DecisionEventKind,
    DecisionReview,
    DecisionStatus,
)
from watchtower.domain.messages import system, user
from watchtower.ports.oracle import Oracle

# --------------------------------------------------------------------------- #
# Explicit capture
# --------------------------------------------------------------------------- #

_CAPTURE_SYSTEM = (
    "You are Watchtower detecting decisions the FOUNDER has explicitly committed to during a "
    "conversation. A decision is an action the founder explicitly chose to take, for example: "
    '"Let\'s do that", "I\'ve decided to build memory", "I\'m going to spend next month '
    'interviewing founders". NEVER treat your own recommendation or suggestion as a decision, '
    "and NEVER infer a decision the founder did not explicitly confirm. If the founder is only "
    "musing, asking, or considering, capture nothing. If there is no explicit commitment, return "
    "an empty list.\n\n"
    "For each real decision, capture what was decided and why, and optionally link supporting "
    "beliefs by their id from the provided list. Respond as a JSON object with key 'decisions': "
    "an array of objects with keys: title (string), question (what was being decided), "
    "chosen_option (string), alternatives_considered (array of strings), reasoning (string), "
    "assumptions (array of strings), expected_outcomes (array of strings), linked_beliefs (array "
    "of belief ids from the provided list)."
)


def capture_decisions(
    conversation: Sequence[str],
    beliefs: Sequence[Belief],
    llm: Oracle,
    *,
    now: datetime | None = None,
) -> tuple[Decision, ...]:
    """Detect decisions the founder explicitly committed to in ``conversation``.

    Returns the captured decisions (status ``accepted``), or an empty tuple when
    the founder made no explicit commitment. Does not mutate anything.
    """
    if not conversation:
        return ()
    belief_ids = {belief.id for belief in beliefs}
    digest = "\n".join(f"- id={belief.id} | {belief.title}" for belief in beliefs)
    prompt = (
        f"Beliefs available to link (reference only):\n{digest or '(none)'}\n\n"
        "Conversation:\n" + "\n".join(conversation)
    )
    data = llm.complete_json([system(_CAPTURE_SYSTEM), user(prompt)])
    moment = now or datetime.now()
    decisions: list[Decision] = []
    for item in data.get("decisions", []):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        linked = tuple(bid for bid in _str_tuple(item.get("linked_beliefs")) if bid in belief_ids)
        decisions.append(
            Decision(
                id=f"decision-{uuid4().hex[:8]}",
                title=title,
                question=str(item.get("question", "")),
                chosen_option=str(item.get("chosen_option", "")),
                alternatives_considered=_str_tuple(item.get("alternatives_considered")),
                reasoning=str(item.get("reasoning", "")),
                linked_beliefs=linked,
                assumptions=_str_tuple(item.get("assumptions")),
                expected_outcomes=_str_tuple(item.get("expected_outcomes")),
                status=DecisionStatus.ACCEPTED,
                created_at=moment,
                updated_at=moment,
                revision=1,
            )
        )
    return tuple(decisions)


def record_decisions(
    store: DecisionStore, decisions: Sequence[Decision], *, now: datetime | None = None
) -> None:
    """Persist newly captured ``decisions`` and log their creation."""
    moment = now or datetime.now()
    for decision in decisions:
        store.upsert(decision)
        store.record_event(
            DecisionEvent(
                decision_id=decision.id,
                kind=DecisionEventKind.CREATED,
                note=decision.title,
                at=moment,
            )
        )


# --------------------------------------------------------------------------- #
# State transitions
# --------------------------------------------------------------------------- #


def mark_completed(
    store: DecisionStore, decision_id: str, *, note: str = "", now: datetime | None = None
) -> Decision | None:
    """Mark a decision completed. Reasoning is preserved, not overwritten."""
    decision = store.get(decision_id)
    if decision is None:
        return None
    moment = now or datetime.now()
    updated = replace(
        decision,
        status=DecisionStatus.COMPLETED,
        updated_at=moment,
        revision=decision.revision + 1,
    )
    store.upsert(updated)
    store.record_event(
        DecisionEvent(
            decision_id=decision_id, kind=DecisionEventKind.COMPLETED, note=note, at=moment
        )
    )
    return updated


# --------------------------------------------------------------------------- #
# Review
# --------------------------------------------------------------------------- #

_REVIEW_SYSTEM = (
    "You are Watchtower reviewing a past decision to improve future judgment - not to judge the "
    "founder. You are given the decision (what was chosen and why, its assumptions and expected "
    "outcomes), the current state of the beliefs that supported it, all current beliefs, and the "
    "evidence observed since. Assess fairly: which assumptions held, which broke, how the "
    "relevant beliefs have changed, and what to learn for next time. Do not fabricate evidence. "
    "Respond as a JSON object with keys: verdict (a short, fair judgment), assumptions_that_held "
    "(array of strings), assumptions_that_broke (array of strings), belief_changes (array "
    "describing how supporting beliefs changed), observed_evidence (array restating the key "
    "evidence), lessons (array of strings), summary (string)."
)


def review_decision(
    decision: Decision,
    beliefs: Sequence[Belief],
    observed_evidence: Sequence[str],
    llm: Oracle,
    *,
    now: datetime | None = None,
) -> DecisionReview:
    """Produce a structured review of ``decision``. Does not mutate anything."""
    linked_ids = set(decision.linked_beliefs)
    linked = [belief for belief in beliefs if belief.id in linked_ids]
    prompt = (
        f"Decision:\n{_decision_digest(decision)}\n\n"
        f"Supporting beliefs, current state:\n{_beliefs_digest(linked) or '(none linked)'}\n\n"
        f"All current beliefs:\n{_beliefs_digest(beliefs) or '(none)'}\n\n"
        f"Observed evidence since the decision:\n{_bullets(observed_evidence) or '(none given)'}"
    )
    data = llm.complete_json([system(_REVIEW_SYSTEM), user(prompt)])
    return DecisionReview(
        decision_id=decision.id,
        verdict=str(data.get("verdict", "")),
        assumptions_that_held=_str_tuple(data.get("assumptions_that_held")),
        assumptions_that_broke=_str_tuple(data.get("assumptions_that_broke")),
        belief_changes=_str_tuple(data.get("belief_changes")),
        observed_evidence=_str_tuple(data.get("observed_evidence")) or tuple(observed_evidence),
        lessons=_str_tuple(data.get("lessons")),
        summary=str(data.get("summary", "")),
        at=now or datetime.now(),
    )


def record_review(
    store: DecisionStore, review: DecisionReview, *, now: datetime | None = None
) -> Decision | None:
    """Persist ``review`` and mark its decision reviewed. Reasoning is preserved."""
    store.record_review(review)
    decision = store.get(review.decision_id)
    if decision is None:
        return None
    moment = now or datetime.now()
    updated = replace(
        decision,
        status=DecisionStatus.REVIEWED,
        updated_at=moment,
        revision=decision.revision + 1,
    )
    store.upsert(updated)
    store.record_event(
        DecisionEvent(
            decision_id=decision.id,
            kind=DecisionEventKind.REVIEWED,
            note=review.summary or review.verdict,
            at=moment,
        )
    )
    return updated


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _decision_digest(decision: Decision) -> str:
    lines = [f"Title: {decision.title}"]
    if decision.chosen_option:
        lines.append(f"Chosen: {decision.chosen_option}")
    if decision.reasoning:
        lines.append(f"Reasoning: {decision.reasoning}")
    if decision.assumptions:
        lines.append("Assumptions:\n" + _bullets(decision.assumptions))
    if decision.expected_outcomes:
        lines.append("Expected outcomes:\n" + _bullets(decision.expected_outcomes))
    return "\n".join(lines)


def _beliefs_digest(beliefs: Sequence[Belief]) -> str:
    return "\n".join(
        f"- id={belief.id} | {belief.title} | confidence={belief.confidence.value} | "
        f"status={belief.status.value}"
        for belief in beliefs
    )


def _bullets(items: Sequence[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _str_tuple(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)
