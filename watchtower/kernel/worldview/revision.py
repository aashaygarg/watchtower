"""Belief revision: the single place beliefs change.

Worldview updates come from one LLM reasoning step over the conversation plus the
current beliefs. This module is the only place beliefs change, so every change
flows through :func:`apply_updates` and is logged. History is never overwritten:
superseding links the old belief to its replacement.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import uuid4

from watchtower.domain.beliefs import (
    Belief,
    BeliefAction,
    BeliefCategory,
    BeliefConfidence,
    BeliefStatus,
    BeliefUpdate,
)
from watchtower.domain.messages import system, user
from watchtower.kernel.worldview.consolidation import ConsolidationAction, consolidate
from watchtower.ports.oracle import Oracle
from watchtower.ports.stores import BeliefStore

_LIVE_STATUSES = (BeliefStatus.ACTIVE, BeliefStatus.WEAKENING)
_CONFIDENCE_ORDER = (BeliefConfidence.LOW, BeliefConfidence.MEDIUM, BeliefConfidence.HIGH)

_UPDATE_SYSTEM = (
    "You are Watchtower updating your worldview after a conversation with the founder. Do NOT "
    "answer the founder. Your only job is to decide how this conversation should change your "
    "beliefs about the founder, company, product, and strategy. Beliefs are conclusions, not a "
    "transcript. Treat every current belief as revisable: change your mind when the evidence "
    "warrants it, and never fabricate evidence.\n\n"
    "You are given your current beliefs (each with an id) and the conversation. Propose only the "
    "changes this conversation justifies. For each, choose one action: create (a genuinely new "
    "belief), strengthen, weaken, supersede (replace an outdated belief with a better one), "
    "disprove, or no_change.\n\n"
    "Respond as a JSON object with key 'updates': an array of objects with keys: action (create, "
    "strengthen, weaken, supersede, disprove, or no_change), belief_id (the id of the existing "
    "belief affected, or null for create), title (a short belief statement, for create or "
    "supersede), description (string), category (product, strategy, customer, founder, "
    "engineering, or market), confidence (low, medium, or high - the resulting confidence), "
    "evidence (array of short observations drawn from the conversation), rationale (string)."
)


def update_beliefs(
    conversation: Sequence[str], beliefs: Sequence[Belief], llm: Oracle
) -> tuple[BeliefUpdate, ...]:
    """Reason about how ``conversation`` should change ``beliefs``.

    Returns proposed updates; it does not mutate anything. Apply them with
    :func:`apply_updates`.
    """
    if not conversation:
        return ()
    digest = _beliefs_digest(beliefs) or "(no beliefs yet)"
    prompt = f"Current beliefs:\n{digest}\n\nConversation:\n" + "\n".join(conversation)
    data = llm.complete_json([system(_UPDATE_SYSTEM), user(prompt)])
    updates = []
    for item in data.get("updates", []):
        if isinstance(item, dict) and item.get("action"):
            updates.append(_parse_update(item))
    return tuple(updates)


def apply_updates(
    store: BeliefStore, updates: Sequence[BeliefUpdate], *, now: datetime | None = None
) -> tuple[BeliefUpdate, ...]:
    """Apply ``updates`` to ``store`` and log each one. Returns the applied updates.

    History is never overwritten: superseding links the old belief to its
    replacement, and every change is recorded in the store's log.
    """
    moment = now or datetime.now()
    applied: list[BeliefUpdate] = []
    for update in updates:
        resolved = _apply_one(store, _guard_destructive(store, update), moment)
        if resolved is not None:
            store.record(resolved)
            applied.append(resolved)
    return tuple(applied)


def _guard_destructive(store: BeliefStore, update: BeliefUpdate) -> BeliefUpdate:
    """Downgrade a destructive change the evidence does not justify.

    A ``supersede`` or ``disprove`` of a HIGH-confidence belief backed only by
    LOW-confidence evidence is downgraded to ``weaken``: a strongly held belief is
    worn down by accumulating doubt, never destroyed by a single weak observation.
    Every other change passes through unchanged.
    """
    if update.action not in (BeliefAction.SUPERSEDE, BeliefAction.DISPROVE):
        return update
    if update.confidence is not BeliefConfidence.LOW:
        return update
    existing = store.get(update.belief_id) if update.belief_id else None
    if existing is None or existing.confidence is not BeliefConfidence.HIGH:
        return update
    return replace(update, action=BeliefAction.WEAKEN)


def _apply_one(store: BeliefStore, update: BeliefUpdate, now: datetime) -> BeliefUpdate | None:
    if update.action is BeliefAction.NO_CHANGE:
        return replace(update, at=now)

    if update.action is BeliefAction.CREATE:
        decision = consolidate(update.title, update.description, store.all())
        if decision.action is ConsolidationAction.SKIP:
            return None
        if decision.action is ConsolidationAction.MERGE and decision.target_id is not None:
            merged = _merge_into(store, decision.target_id, update, now)
            if merged is not None:
                return merged
        belief = _new_belief(update, now)
        store.upsert(belief)
        return replace(update, belief_id=belief.id, at=now)

    if update.action is BeliefAction.SUPERSEDE:
        replacement = _new_belief(update, now)
        store.upsert(replacement)
        existing = store.get(update.belief_id) if update.belief_id else None
        if existing is not None:
            store.upsert(
                replace(
                    existing,
                    status=BeliefStatus.SUPERSEDED,
                    superseded_by=replacement.id,
                    updated_at=now,
                    revision=existing.revision + 1,
                )
            )
        return replace(update, at=now)

    existing = store.get(update.belief_id) if update.belief_id else None
    if existing is None:
        return None  # nothing to change

    if update.action is BeliefAction.STRENGTHEN:
        store.upsert(
            replace(
                existing,
                confidence=update.confidence or _stronger(existing.confidence),
                supporting_evidence=existing.supporting_evidence + update.evidence,
                status=BeliefStatus.ACTIVE,
                updated_at=now,
                revision=existing.revision + 1,
            )
        )
    elif update.action is BeliefAction.WEAKEN:
        store.upsert(
            replace(
                existing,
                confidence=update.confidence or _weaker(existing.confidence),
                contradicting_evidence=existing.contradicting_evidence + update.evidence,
                status=BeliefStatus.WEAKENING,
                updated_at=now,
                revision=existing.revision + 1,
            )
        )
    elif update.action is BeliefAction.DISPROVE:
        store.upsert(
            replace(
                existing,
                confidence=BeliefConfidence.LOW,
                contradicting_evidence=existing.contradicting_evidence + update.evidence,
                status=BeliefStatus.DISPROVEN,
                updated_at=now,
                revision=existing.revision + 1,
            )
        )
    return replace(update, at=now)


def _merge_into(
    store: BeliefStore, target_id: str, update: BeliefUpdate, now: datetime
) -> BeliefUpdate | None:
    """Fold a duplicate candidate into an existing belief by strengthening it.

    The candidate's evidence is added to the target and its confidence is raised,
    so a restated belief reinforces the one already held instead of spawning a
    duplicate. Returns the change as a ``strengthen`` for the log.
    """
    existing = store.get(target_id)
    if existing is None:
        return None
    store.upsert(
        replace(
            existing,
            confidence=update.confidence or _stronger(existing.confidence),
            supporting_evidence=existing.supporting_evidence + update.evidence,
            status=BeliefStatus.ACTIVE,
            updated_at=now,
            revision=existing.revision + 1,
        )
    )
    return replace(update, action=BeliefAction.STRENGTHEN, belief_id=target_id, at=now)


def _new_belief(update: BeliefUpdate, now: datetime) -> Belief:
    return Belief(
        id=f"belief-{uuid4().hex[:8]}",
        title=update.title or "(untitled belief)",
        description=update.description,
        category=update.category or BeliefCategory.STRATEGY,
        confidence=update.confidence or BeliefConfidence.MEDIUM,
        supporting_evidence=update.evidence,
        status=BeliefStatus.ACTIVE,
        created_at=now,
        updated_at=now,
        revision=1,
    )


def _beliefs_digest(beliefs: Sequence[Belief]) -> str:
    return "\n".join(
        f"- id={b.id} | {b.title} | confidence={b.confidence.value} | status={b.status.value}"
        for b in beliefs
        if b.status in _LIVE_STATUSES
    )


def _parse_update(item: dict[str, Any]) -> BeliefUpdate:
    return BeliefUpdate(
        action=_parse_action(item.get("action")),
        rationale=str(item.get("rationale", "")),
        belief_id=str(item["belief_id"]) if item.get("belief_id") else None,
        title=str(item.get("title", "")),
        description=str(item.get("description", "")),
        category=_parse_enum(BeliefCategory, item.get("category")),
        confidence=_parse_enum(BeliefConfidence, item.get("confidence")),
        evidence=_str_tuple(item.get("evidence")),
    )


def _parse_action(value: Any) -> BeliefAction:
    try:
        return BeliefAction(str(value).strip().lower())
    except ValueError:
        return BeliefAction.NO_CHANGE


def _parse_enum(enum_cls: Any, value: Any) -> Any:
    if not value:
        return None
    try:
        return enum_cls(str(value).strip().lower())
    except ValueError:
        return None


def _stronger(confidence: BeliefConfidence) -> BeliefConfidence:
    index = _CONFIDENCE_ORDER.index(confidence)
    return _CONFIDENCE_ORDER[min(index + 1, len(_CONFIDENCE_ORDER) - 1)]


def _weaker(confidence: BeliefConfidence) -> BeliefConfidence:
    index = _CONFIDENCE_ORDER.index(confidence)
    return _CONFIDENCE_ORDER[max(index - 1, 0)]


def _str_tuple(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)
