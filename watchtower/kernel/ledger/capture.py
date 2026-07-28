"""Decision capture: recording the commitments a founder explicitly makes.

A decision is captured only when the founder explicitly chose to take an action -
never inferred from Watchtower's own recommendation. Beliefs may be linked by id
for reference, but they are never mutated here.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import uuid4

from watchtower.domain.beliefs import Belief
from watchtower.domain.decisions import (
    Decision,
    DecisionEventKind,
    DecisionStatus,
)
from watchtower.domain.messages import system, user
from watchtower.kernel.ledger.events import make_event
from watchtower.ports.oracle import Oracle
from watchtower.ports.stores import DecisionStore

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
            make_event(
                decision.id,
                DecisionEventKind.CREATED,
                note=decision.title,
                at=moment,
            )
        )


def _str_tuple(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)
