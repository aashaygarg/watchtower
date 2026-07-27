"""Tests for the decision engine: model, store, capture, transitions, review."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from typer.testing import CliRunner
from watchtower.beliefs import Belief, BeliefCategory, BeliefConfidence
from watchtower.cli import app
from watchtower.decisions import (
    Decision,
    DecisionEventKind,
    DecisionStatus,
    JsonDecisionStore,
    capture_decisions,
    mark_completed,
    record_decisions,
    record_review,
    review_decision,
)
from watchtower.llm import Message

runner = CliRunner()


class FakeLLM:
    """Returns a canned JSON response for capture or review."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def complete(self, messages: Sequence[Message]) -> str:
        return "ok"

    def complete_json(self, messages: Sequence[Message]) -> dict[str, Any]:
        return self.response


def _belief(belief_id: str = "b1", title: str = "Memory is the bottleneck") -> Belief:
    return Belief(
        id=belief_id,
        title=title,
        category=BeliefCategory.PRODUCT,
        confidence=BeliefConfidence.MEDIUM,
    )


def _decision(**kwargs: Any) -> Decision:
    defaults: dict[str, Any] = {
        "id": "d1",
        "title": "Build memory next",
        "chosen_option": "Build memory",
        "reasoning": "Users keep re-explaining context.",
        "assumptions": ("Users want continuity.",),
        "status": DecisionStatus.ACCEPTED,
        "created_at": datetime(2026, 7, 28, 9, 0, 0),
        "updated_at": datetime(2026, 7, 28, 9, 0, 0),
    }
    defaults.update(kwargs)
    return Decision(**defaults)


def test_json_store_roundtrip(tmp_path: Path) -> None:
    store = JsonDecisionStore(tmp_path / "decisions.json")
    decision = _decision(
        alternatives_considered=("do nothing",),
        linked_beliefs=("b1",),
        expected_outcomes=("higher retention",),
    )
    store.upsert(decision)

    reloaded = JsonDecisionStore(tmp_path / "decisions.json")
    loaded = reloaded.get("d1")

    assert loaded is not None
    assert loaded.title == "Build memory next"
    assert loaded.status is DecisionStatus.ACCEPTED
    assert loaded.linked_beliefs == ("b1",)
    assert loaded.assumptions == ("Users want continuity.",)
    assert loaded.created_at == decision.created_at


def test_capture_on_explicit_commitment() -> None:
    llm = FakeLLM(
        {
            "decisions": [
                {
                    "title": "Interview ten founders next month",
                    "question": "How do we validate demand?",
                    "chosen_option": "Interview founders",
                    "reasoning": "We need evidence before building.",
                    "assumptions": ["Founders will talk to us"],
                    "expected_outcomes": ["A clear signal on demand"],
                    "linked_beliefs": ["b1", "does-not-exist"],
                }
            ]
        }
    )
    conversation = ["You: I'm going to spend next month interviewing founders."]

    decisions = capture_decisions(conversation, [_belief("b1")], llm)

    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.status is DecisionStatus.ACCEPTED  # explicit founder commitment
    assert decision.title == "Interview ten founders next month"
    assert decision.linked_beliefs == ("b1",)  # unknown belief ids are dropped


def test_capture_returns_nothing_without_commitment() -> None:
    llm = FakeLLM({"decisions": []})
    decisions = capture_decisions(["You: what do you think about memory?"], [_belief()], llm)
    assert decisions == ()


def test_capture_does_not_touch_beliefs() -> None:
    belief = _belief("b1")
    llm = FakeLLM({"decisions": [{"title": "Do X", "linked_beliefs": ["b1"]}]})

    capture_decisions(["You: let's do X"], [belief], llm)

    # Beliefs are immutable and never passed to a belief store here.
    assert belief.confidence is BeliefConfidence.MEDIUM


def test_record_and_complete_preserves_reasoning(tmp_path: Path) -> None:
    store = JsonDecisionStore(tmp_path / "decisions.json")
    record_decisions(store, [_decision()])

    assert store.get("d1") is not None
    assert store.events()[-1].kind is DecisionEventKind.CREATED

    completed = mark_completed(store, "d1")
    assert completed is not None
    assert completed.status is DecisionStatus.COMPLETED
    assert completed.reasoning == "Users keep re-explaining context."  # reasoning preserved
    assert completed.revision == 2
    assert store.events()[-1].kind is DecisionEventKind.COMPLETED


def test_review_produces_structured_review(tmp_path: Path) -> None:
    store = JsonDecisionStore(tmp_path / "decisions.json")
    record_decisions(store, [_decision(linked_beliefs=("b1",))])

    llm = FakeLLM(
        {
            "verdict": "Premature",
            "assumptions_that_held": ["Users engaged"],
            "assumptions_that_broke": ["Users wanted continuity"],
            "belief_changes": ["Memory belief weakened to low"],
            "lessons": ["Validate demand before building"],
            "summary": "The decision ran ahead of the evidence.",
        }
    )
    review = review_decision(store.get("d1"), [_belief("b1")], ["No user asked for memory"], llm)
    updated = record_review(store, review)

    assert review.verdict == "Premature"
    assert review.assumptions_that_broke == ("Users wanted continuity",)
    assert review.observed_evidence  # falls back to the founder's observations
    assert updated is not None
    assert updated.status is DecisionStatus.REVIEWED
    assert store.reviews()[-1].summary == "The decision ran ahead of the evidence."
    assert store.events()[-1].kind is DecisionEventKind.REVIEWED


def test_history_is_append_only(tmp_path: Path) -> None:
    store = JsonDecisionStore(tmp_path / "decisions.json")
    record_decisions(store, [_decision()])
    mark_completed(store, "d1")
    review = review_decision(store.get("d1"), [], [], FakeLLM({"summary": "ok"}))
    record_review(store, review)

    kinds = [event.kind for event in store.events()]
    assert kinds == [
        DecisionEventKind.CREATED,
        DecisionEventKind.COMPLETED,
        DecisionEventKind.REVIEWED,
    ]


def test_decisions_command_lists_sections(tmp_path: Path) -> None:
    store = JsonDecisionStore(tmp_path / ".watchtower" / "decisions.json")
    record_decisions(store, [_decision(id="d1", title="Build memory next")])
    record_decisions(store, [_decision(id="d2", title="Hire a designer")])
    mark_completed(store, "d2")

    result = runner.invoke(app, ["decisions", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert "Build memory next" in result.stdout
    assert "Hire a designer" in result.stdout
    assert "Active decisions" in result.stdout
    assert "Completed decisions" in result.stdout


def test_complete_command(tmp_path: Path) -> None:
    store = JsonDecisionStore(tmp_path / ".watchtower" / "decisions.json")
    record_decisions(store, [_decision(id="d1")])

    result = runner.invoke(app, ["complete", "d1", "--path", str(tmp_path)])

    assert result.exit_code == 0
    reloaded = JsonDecisionStore(tmp_path / ".watchtower" / "decisions.json")
    assert reloaded.get("d1").status is DecisionStatus.COMPLETED


def test_review_command_unknown_decision(tmp_path: Path) -> None:
    result = runner.invoke(app, ["review", "nope", "--path", str(tmp_path)])
    assert result.exit_code == 1
