"""Tests for the pure startup domain model.

These tests verify structural guarantees (immutability, defaults, identity
references) only — the domain objects intentionally carry no behavior yet.
"""

from __future__ import annotations

import dataclasses

import pytest
from watchtower.startup import (
    Evidence,
    EvidenceId,
    EvidenceStance,
    Goal,
    GoalId,
    GoalStatus,
    Hypothesis,
    HypothesisId,
    HypothesisStatus,
    Startup,
    StartupId,
    StartupStage,
)


def test_startup_defaults() -> None:
    startup = Startup(id=StartupId("s1"), name="Acme")

    assert startup.stage is StartupStage.IDEA
    assert startup.goal_ids == ()
    assert startup.mission == ""


def test_entities_are_frozen() -> None:
    startup = Startup(id=StartupId("s1"), name="Acme")

    with pytest.raises(dataclasses.FrozenInstanceError):
        startup.name = "Beta"  # type: ignore[misc]


def test_entities_require_keyword_arguments() -> None:
    with pytest.raises(TypeError):
        Startup(StartupId("s1"), "Acme")  # type: ignore[misc]


def test_goal_references_startup_by_id() -> None:
    goal = Goal(id=GoalId("g1"), startup_id=StartupId("s1"), title="Reach PMF")

    assert goal.status is GoalStatus.PROPOSED
    assert goal.strategy_ids == ()


def test_hypothesis_and_evidence_link_by_id() -> None:
    hypothesis = Hypothesis(id=HypothesisId("h1"), statement="Users want X")
    evidence = Evidence(
        id=EvidenceId("e1"),
        summary="10/10 interviewees asked for X",
        stance=EvidenceStance.SUPPORTS,
        hypothesis_id=hypothesis.id,
    )

    assert hypothesis.status is HypothesisStatus.UNTESTED
    assert hypothesis.confidence == 0.5
    assert evidence.hypothesis_id == hypothesis.id
