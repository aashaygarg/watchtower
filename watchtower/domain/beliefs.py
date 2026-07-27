"""Belief domain model: Watchtower's evolving worldview.

Beliefs are conclusions distilled from conversations, not a transcript of them.
They are pure, immutable, serializable data - independent of conversations,
storage, retrieval, and the LLM. A change produces a new immutable value; history
is preserved by the store's append-only update log, never by silent mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class BeliefCategory(StrEnum):
    """What a belief is about."""

    PRODUCT = "product"
    STRATEGY = "strategy"
    CUSTOMER = "customer"
    FOUNDER = "founder"
    ENGINEERING = "engineering"
    MARKET = "market"


class BeliefConfidence(StrEnum):
    """How strongly a belief is held. Qualitative, never a percentage."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BeliefStatus(StrEnum):
    """Lifecycle state of a belief."""

    ACTIVE = "active"
    WEAKENING = "weakening"
    SUPERSEDED = "superseded"
    DISPROVEN = "disproven"


class BeliefAction(StrEnum):
    """A change the worldview-update step can make to a belief."""

    CREATE = "create"
    STRENGTHEN = "strengthen"
    WEAKEN = "weaken"
    SUPERSEDE = "supersede"
    DISPROVE = "disprove"
    NO_CHANGE = "no_change"


@dataclass(frozen=True, slots=True, kw_only=True)
class Belief:
    """A single conclusion Watchtower holds about the founder's world.

    Attributes:
        id: Stable unique identifier.
        title: A one-line statement of the belief.
        description: Longer explanation.
        category: What the belief is about.
        confidence: How strongly it is held.
        supporting_evidence: Observations that support it.
        contradicting_evidence: Observations that argue against it.
        assumptions: What the belief takes for granted.
        status: Lifecycle state.
        created_at: When the belief was first formed.
        updated_at: When the belief last changed.
        revision: How many times the belief has changed (starts at 1).
        superseded_by: The id of the belief that replaced this one, if any.
    """

    id: str
    title: str
    description: str = ""
    category: BeliefCategory = BeliefCategory.STRATEGY
    confidence: BeliefConfidence = BeliefConfidence.MEDIUM
    supporting_evidence: tuple[str, ...] = ()
    contradicting_evidence: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    status: BeliefStatus = BeliefStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None
    revision: int = 1
    superseded_by: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class BeliefUpdate:
    """One proposed or applied change to the worldview, with its rationale.

    Instances are produced by the worldview-update step and appended to the
    store's log so every change to a belief is traceable.

    Attributes:
        action: The change to make.
        rationale: Why the change is warranted, grounded in the conversation.
        belief_id: The existing belief affected (or the created belief, once applied).
        title: A belief statement, for ``create`` and ``supersede``.
        description: Longer explanation, for ``create`` and ``supersede``.
        category: The belief's category, for ``create`` and ``supersede``.
        confidence: The resulting confidence, when the action changes it.
        evidence: Short observations drawn from the conversation.
        at: When the update was applied.
    """

    action: BeliefAction
    rationale: str = ""
    belief_id: str | None = None
    title: str = ""
    description: str = ""
    category: BeliefCategory | None = None
    confidence: BeliefConfidence | None = None
    evidence: tuple[str, ...] = ()
    at: datetime | None = None
