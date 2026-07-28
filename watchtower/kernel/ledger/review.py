"""Decision transitions and review: completion and after-the-fact assessment.

Completing or reviewing a decision preserves its original reasoning; state
changes are appended to the store's event log rather than overwriting anything. A
review reads the beliefs that supported the decision to judge, fairly, which
assumptions held and what to learn - it never mutates a belief.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from typing import Any

from watchtower.domain.beliefs import Belief
from watchtower.domain.decisions import (
    Decision,
    DecisionEventKind,
    DecisionReview,
    DecisionStatus,
)
from watchtower.domain.messages import system, user
from watchtower.kernel.ledger.events import make_event
from watchtower.ports.oracle import Oracle
from watchtower.ports.stores import DecisionStore


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
    store.record_event(make_event(decision_id, DecisionEventKind.COMPLETED, note=note, at=moment))
    return updated


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
        make_event(
            decision.id,
            DecisionEventKind.REVIEWED,
            note=review.summary or review.verdict,
            at=moment,
        )
    )
    return updated


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
