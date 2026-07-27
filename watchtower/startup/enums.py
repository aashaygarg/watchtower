"""Enumerations for the Watchtower founder-operating-system domain.

These enums capture the lifecycle states and categorical attributes of the core
domain entities. They are plain :class:`enum.Enum` subclasses backed by strings
so that they remain trivially serializable and framework-agnostic. No behavior
is attached — they only enumerate the valid values a field may take.
"""

from __future__ import annotations

from enum import StrEnum


class StartupStage(StrEnum):
    """The maturity stage of a :class:`~watchtower.startup.models.Startup`."""

    IDEA = "idea"
    PRE_SEED = "pre_seed"
    SEED = "seed"
    SERIES_A = "series_a"
    GROWTH = "growth"
    SCALE = "scale"


class GoalStatus(StrEnum):
    """Lifecycle state of a :class:`~watchtower.startup.models.Goal`."""

    PROPOSED = "proposed"
    ACTIVE = "active"
    ACHIEVED = "achieved"
    BLOCKED = "blocked"
    ABANDONED = "abandoned"


class StrategyStatus(StrEnum):
    """Lifecycle state of a :class:`~watchtower.startup.models.Strategy`."""

    PROPOSED = "proposed"
    ACTIVE = "active"
    PAUSED = "paused"
    VALIDATED = "validated"
    INVALIDATED = "invalidated"
    ABANDONED = "abandoned"


class HypothesisStatus(StrEnum):
    """Test state of a :class:`~watchtower.startup.models.Hypothesis`."""

    UNTESTED = "untested"
    TESTING = "testing"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    INCONCLUSIVE = "inconclusive"


class ExperimentStatus(StrEnum):
    """Lifecycle state of an :class:`~watchtower.startup.models.Experiment`."""

    DESIGNED = "designed"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class EvidenceStance(StrEnum):
    """Whether a piece of evidence supports or refutes a hypothesis."""

    SUPPORTS = "supports"
    REFUTES = "refutes"
    NEUTRAL = "neutral"


class EvidenceSource(StrEnum):
    """The origin of a piece of :class:`~watchtower.startup.models.Evidence`."""

    CUSTOMER_INTERVIEW = "customer_interview"
    USAGE_ANALYTICS = "usage_analytics"
    EXPERIMENT = "experiment"
    MARKET_RESEARCH = "market_research"
    FINANCIAL = "financial"
    EXPERT_OPINION = "expert_opinion"
    ANECDOTAL = "anecdotal"
    OTHER = "other"


class DecisionStatus(StrEnum):
    """Lifecycle state of a :class:`~watchtower.startup.models.Decision`."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    REVISITED = "revisited"
