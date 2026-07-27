"""Core domain model for the Watchtower founder operating system.

This module defines the *pure* domain entities that Watchtower reasons about: a
:class:`Startup` and the artifacts a founder uses to steer it — :class:`Goal`,
:class:`Strategy`, :class:`Hypothesis`, :class:`Evidence`, :class:`Experiment`,
and :class:`Decision`.

Design principles
-----------------
* **Immutable.** Every entity is a frozen dataclass; collections are ``tuple``
  rather than ``list``. State transitions are modeled by constructing new
  values, never by mutating existing ones.
* **Pure.** These objects have no methods, no validation logic, no I/O, no LLM
  calls, and no orchestration dependencies. They are plain data.
* **Framework-agnostic.** Nothing here imports LangGraph, Pydantic, or any
  persistence layer. The model stays valid if the orchestration framework is
  replaced. Only the Python standard library is used.
* **Referenced by identity.** Entities refer to one another by strongly-typed
  identifiers (``NewType`` aliases over ``str``) rather than by object
  composition. This keeps the graph flat, easy to persist, and cheap to update
  immutably, and it avoids deep nested structures that are awkward to rebuild.

Behavior (state machines, scoring, persistence, orchestration) belongs in
separate layers and is intentionally not implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import NewType

from watchtower.startup.enums import (
    DecisionStatus,
    EvidenceSource,
    EvidenceStance,
    ExperimentStatus,
    GoalStatus,
    HypothesisStatus,
    StartupStage,
    StrategyStatus,
)

# --------------------------------------------------------------------------- #
# Identifiers
#
# Distinct ``NewType`` aliases give each entity its own identifier type. They
# are ``str`` at runtime but let type checkers catch mistakes such as passing a
# ``GoalId`` where a ``StrategyId`` is expected.
# --------------------------------------------------------------------------- #

StartupId = NewType("StartupId", str)
GoalId = NewType("GoalId", str)
StrategyId = NewType("StrategyId", str)
HypothesisId = NewType("HypothesisId", str)
EvidenceId = NewType("EvidenceId", str)
ExperimentId = NewType("ExperimentId", str)
DecisionId = NewType("DecisionId", str)


@dataclass(frozen=True, slots=True, kw_only=True)
class Startup:
    """The top-level entity a founder operates through Watchtower.

    A ``Startup`` is the root of the domain graph. It owns a set of goals and
    carries the framing context (mission, stage) against which every other
    artifact is interpreted.

    Attributes:
        id: Stable unique identifier for the startup.
        name: Human-readable name of the venture.
        mission: One-line statement of what the startup is trying to achieve.
        stage: Current maturity stage. Defaults to :attr:`StartupStage.IDEA`.
        founded_on: Calendar date the startup was founded, if known.
        goal_ids: Identifiers of the goals this startup is pursuing.
        tags: Free-form labels for grouping and filtering.
        created_at: When this record was created, if tracked by the caller.
    """

    id: StartupId
    name: str
    mission: str = ""
    stage: StartupStage = StartupStage.IDEA
    founded_on: date | None = None
    goal_ids: tuple[GoalId, ...] = ()
    tags: tuple[str, ...] = ()
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Goal:
    """A measurable outcome the startup intends to reach.

    Goals express *what* success looks like. They may form a hierarchy via
    :attr:`parent_goal_id`, and are pursued through one or more strategies.

    Attributes:
        id: Stable unique identifier for the goal.
        startup_id: The startup this goal belongs to.
        title: Short statement of the desired outcome.
        description: Longer explanation of the goal and its rationale.
        status: Lifecycle state. Defaults to :attr:`GoalStatus.PROPOSED`.
        target_metric: Name of the metric used to judge success, if any.
        target_value: Target value for ``target_metric`` expressed as text so
            any unit or format can be represented without coupling to a schema.
        due_on: Date by which the goal should be met, if time-boxed.
        parent_goal_id: Parent goal when this goal is a sub-goal.
        strategy_ids: Identifiers of the strategies pursuing this goal.
        tags: Free-form labels for grouping and filtering.
        created_at: When this record was created, if tracked by the caller.
    """

    id: GoalId
    startup_id: StartupId
    title: str
    description: str = ""
    status: GoalStatus = GoalStatus.PROPOSED
    target_metric: str | None = None
    target_value: str | None = None
    due_on: date | None = None
    parent_goal_id: GoalId | None = None
    strategy_ids: tuple[StrategyId, ...] = ()
    tags: tuple[str, ...] = ()
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Strategy:
    """A chosen approach for achieving a goal.

    A strategy describes *how* a goal will be pursued. It is the bridge between
    an outcome (:class:`Goal`) and the testable beliefs (:class:`Hypothesis`)
    that must hold for the approach to work.

    Attributes:
        id: Stable unique identifier for the strategy.
        goal_id: The goal this strategy serves.
        title: Short name for the approach.
        description: Longer explanation of the approach and its reasoning.
        status: Lifecycle state. Defaults to :attr:`StrategyStatus.PROPOSED`.
        hypothesis_ids: Identifiers of the hypotheses this strategy depends on.
        tags: Free-form labels for grouping and filtering.
        created_at: When this record was created, if tracked by the caller.
    """

    id: StrategyId
    goal_id: GoalId
    title: str
    description: str = ""
    status: StrategyStatus = StrategyStatus.PROPOSED
    hypothesis_ids: tuple[HypothesisId, ...] = ()
    tags: tuple[str, ...] = ()
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Hypothesis:
    """A testable belief that a strategy relies on.

    Hypotheses make a strategy's assumptions explicit so they can be validated
    or refuted through experiments and evidence.

    Attributes:
        id: Stable unique identifier for the hypothesis.
        statement: The belief expressed as a falsifiable statement.
        strategy_id: The strategy this hypothesis supports, if any.
        status: Test state. Defaults to :attr:`HypothesisStatus.UNTESTED`.
        confidence: Current subjective confidence that the hypothesis holds,
            expressed on a ``0.0`` to ``1.0`` scale.
        rationale: Why this hypothesis is believed or worth testing.
        experiment_ids: Identifiers of experiments designed to test it.
        evidence_ids: Identifiers of evidence bearing on it.
        tags: Free-form labels for grouping and filtering.
        created_at: When this record was created, if tracked by the caller.
    """

    id: HypothesisId
    statement: str
    strategy_id: StrategyId | None = None
    status: HypothesisStatus = HypothesisStatus.UNTESTED
    confidence: float = 0.5
    rationale: str = ""
    experiment_ids: tuple[ExperimentId, ...] = ()
    evidence_ids: tuple[EvidenceId, ...] = ()
    tags: tuple[str, ...] = ()
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Evidence:
    """An observation that bears on a hypothesis.

    Evidence records a single datum — an interview quote, a metric movement, a
    market signal — together with its stance and reliability. It is the raw
    material from which confidence in a hypothesis is updated.

    Attributes:
        id: Stable unique identifier for the evidence.
        summary: Short description of what was observed.
        stance: Whether the observation supports, refutes, or is neutral toward
            the associated hypothesis. Defaults to :attr:`EvidenceStance.NEUTRAL`.
        source: Category of origin. Defaults to :attr:`EvidenceSource.OTHER`.
        strength: How strong or reliable the evidence is, expressed on a
            ``0.0`` to ``1.0`` scale.
        hypothesis_id: The hypothesis this evidence bears on, if any.
        experiment_id: The experiment that produced this evidence, if any.
        detail: Longer verbatim detail, quote, or notes.
        source_reference: Citation, link, or pointer to the raw source.
        observed_at: When the observation was made, if known.
        tags: Free-form labels for grouping and filtering.
        created_at: When this record was created, if tracked by the caller.
    """

    id: EvidenceId
    summary: str
    stance: EvidenceStance = EvidenceStance.NEUTRAL
    source: EvidenceSource = EvidenceSource.OTHER
    strength: float = 0.5
    hypothesis_id: HypothesisId | None = None
    experiment_id: ExperimentId | None = None
    detail: str = ""
    source_reference: str | None = None
    observed_at: datetime | None = None
    tags: tuple[str, ...] = ()
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Experiment:
    """A deliberate test designed to produce evidence about a hypothesis.

    An experiment defines what will be done and how success is judged. Running
    it yields :class:`Evidence` that updates confidence in the hypothesis.

    Attributes:
        id: Stable unique identifier for the experiment.
        name: Short name for the experiment.
        hypothesis_id: The hypothesis this experiment is designed to test.
        description: What the experiment does and how it is run.
        status: Lifecycle state. Defaults to :attr:`ExperimentStatus.DESIGNED`.
        success_criteria: The observable condition that would count as success.
        started_at: When the experiment began, if started.
        ended_at: When the experiment concluded, if finished.
        evidence_ids: Identifiers of evidence produced by the experiment.
        tags: Free-form labels for grouping and filtering.
        created_at: When this record was created, if tracked by the caller.
    """

    id: ExperimentId
    name: str
    hypothesis_id: HypothesisId
    description: str = ""
    status: ExperimentStatus = ExperimentStatus.DESIGNED
    success_criteria: str = ""
    started_at: datetime | None = None
    ended_at: datetime | None = None
    evidence_ids: tuple[EvidenceId, ...] = ()
    tags: tuple[str, ...] = ()
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Decision:
    """A recorded choice made in steering the startup.

    A decision captures the context, the options weighed, the option chosen, and
    the reasoning — an append-only record that can be superseded but never
    silently rewritten. Decisions may reference the goal, strategy, hypothesis,
    and evidence that informed them.

    Attributes:
        id: Stable unique identifier for the decision.
        title: Short statement of what was decided.
        context: The situation and forces that prompted the decision.
        options_considered: The alternatives that were weighed.
        chosen_option: The option that was selected.
        rationale: Why the chosen option was preferred.
        status: Lifecycle state. Defaults to :attr:`DecisionStatus.PROPOSED`.
        reversible: Whether the decision can be readily undone.
        goal_id: The goal this decision relates to, if any.
        strategy_id: The strategy this decision relates to, if any.
        hypothesis_id: The hypothesis this decision relates to, if any.
        supporting_evidence_ids: Evidence cited in support of the decision.
        superseded_by: The decision that replaces this one, if any.
        decided_at: When the decision was made, if recorded.
        tags: Free-form labels for grouping and filtering.
        created_at: When this record was created, if tracked by the caller.
    """

    id: DecisionId
    title: str
    context: str = ""
    options_considered: tuple[str, ...] = ()
    chosen_option: str = ""
    rationale: str = ""
    status: DecisionStatus = DecisionStatus.PROPOSED
    reversible: bool = True
    goal_id: GoalId | None = None
    strategy_id: StrategyId | None = None
    hypothesis_id: HypothesisId | None = None
    supporting_evidence_ids: tuple[EvidenceId, ...] = ()
    superseded_by: DecisionId | None = None
    decided_at: datetime | None = None
    tags: tuple[str, ...] = ()
    created_at: datetime | None = None
