"""On-write belief consolidation: fold a near-duplicate belief into an existing one.

When the worldview-update step would CREATE a belief, consolidation asks a prior
question: is this genuinely new, or does it restate something already believed?
The signal is lexical - token overlap against existing live beliefs, the same
signal used for relevance - so no embeddings or vector store are involved.

Outcomes:

- ``CREATE``: no live belief is close enough; record the new belief.
- ``MERGE``:  a live belief is highly similar; strengthen it instead of duplicating.
- ``SKIP``:   the candidate carries no usable content; drop it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from watchtower.domain.beliefs import Belief, BeliefStatus
from watchtower.kernel.worldview.relevance import _tokens

_LIVE_STATUSES = (BeliefStatus.ACTIVE, BeliefStatus.WEAKENING)
#: Jaccard token overlap at or above which two beliefs are treated as the same belief.
_MERGE_THRESHOLD = 0.6


class ConsolidationAction(StrEnum):
    """What to do with a candidate belief on write."""

    CREATE = "create"
    MERGE = "merge"
    SKIP = "skip"


@dataclass(frozen=True, slots=True)
class ConsolidationDecision:
    """The on-write decision for a candidate belief.

    Attributes:
        action: Whether to create it, merge it into an existing belief, or skip it.
        target_id: The belief to merge into, when ``action`` is ``MERGE``.
    """

    action: ConsolidationAction
    target_id: str | None = None


def consolidate(title: str, description: str, beliefs: Sequence[Belief]) -> ConsolidationDecision:
    """Decide whether a candidate belief is new, a duplicate to merge, or empty.

    The candidate is compared by lexical token overlap against every live belief.
    The most similar belief at or above the merge threshold wins a ``MERGE``;
    otherwise the candidate is genuinely new and gets a ``CREATE``. A candidate
    with no meaningful tokens is ``SKIP``ped.
    """
    candidate = _tokens(f"{title} {description}")
    if not candidate:
        return ConsolidationDecision(ConsolidationAction.SKIP)
    best_id: str | None = None
    best_score = 0.0
    for belief in beliefs:
        if belief.status not in _LIVE_STATUSES:
            continue
        score = _jaccard(candidate, _tokens(f"{belief.title} {belief.description}"))
        if score > best_score:
            best_id, best_score = belief.id, score
    if best_id is not None and best_score >= _MERGE_THRESHOLD:
        return ConsolidationDecision(ConsolidationAction.MERGE, target_id=best_id)
    return ConsolidationDecision(ConsolidationAction.CREATE)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
