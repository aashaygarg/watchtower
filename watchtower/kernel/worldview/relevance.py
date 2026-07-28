"""Belief relevance: which beliefs to surface, without embeddings.

Relevance is simple lexical token overlap between the founder's message and each
belief's title, description, and category. Superseded and disproven beliefs are
never surfaced. No embeddings, vector search, retrieval, or agents are involved.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from watchtower.domain.beliefs import Belief, BeliefConfidence, BeliefStatus

_LIVE_STATUSES = (BeliefStatus.ACTIVE, BeliefStatus.WEAKENING)
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "are",
        "for",
        "our",
        "should",
        "you",
        "your",
        "with",
        "about",
        "what",
        "how",
        "does",
        "did",
        "this",
        "that",
        "have",
        "has",
        "not",
        "but",
        "can",
        "will",
        "would",
        "into",
        "from",
        "they",
        "them",
        "its",
        "was",
        "were",
    }
)


def select_relevant(beliefs: Sequence[Belief], text: str, *, limit: int = 5) -> tuple[Belief, ...]:
    """Return the live beliefs most lexically relevant to ``text``.

    Relevance is token overlap between ``text`` and each belief's title,
    description, and category. Superseded and disproven beliefs are never
    injected. No embeddings or vector search are involved.
    """
    query = _tokens(text)
    if not query:
        return ()
    scored: list[tuple[int, Belief]] = []
    for belief in beliefs:
        if belief.status not in _LIVE_STATUSES:
            continue
        haystack = f"{belief.title} {belief.description} {belief.category.value}"
        overlap = len(query & _tokens(haystack))
        if overlap:
            scored.append((overlap, belief))
    scored.sort(
        key=lambda pair: (pair[0], pair[1].confidence == BeliefConfidence.HIGH),
        reverse=True,
    )
    return tuple(belief for _, belief in scored[:limit])


def format_for_prompt(beliefs: Sequence[Belief]) -> tuple[str, ...]:
    """Render beliefs as one line each for injection into a conversation."""
    lines = []
    for belief in beliefs:
        line = f"[{belief.confidence.value}] {belief.title}"
        if belief.description:
            line += f" - {belief.description}"
        lines.append(line)
    return tuple(lines)


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {word for word in words if len(word) > 2 and word not in _STOPWORDS}
