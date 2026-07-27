"""Tests for the dialogue engine and the LLM seam."""

from __future__ import annotations

import inspect
from collections.abc import Sequence
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console
from watchtower.cli.conversation import render_thinking
from watchtower.cognition import think
from watchtower.config import LLMConfig
from watchtower.domain.judgment import ConfidenceReason, Experiment, ThinkingResult
from watchtower.domain.messages import Message
from watchtower.llm import LLMUnavailableError, build_llm
from watchtower.startup.models import Startup, StartupId
from watchtower.startup.workspace import StartupWorkspace


def _workspace() -> StartupWorkspace:
    return StartupWorkspace(
        root=Path("."),
        startup=Startup(id=StartupId("healthos"), name="HealthOS", mission="Make health simple."),
        vision="",
    )


class FakeLLM:
    """Returns one canned dialogue turn and records the messages it received."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls = 0
        self.messages: list[Message] = []

    def complete(self, messages: Sequence[Message]) -> str:
        return "ok"

    def complete_json(self, messages: Sequence[Message]) -> dict[str, Any]:
        self.calls += 1
        self.messages = list(messages)
        return self.response


_DIALOGUE_TURN = {
    "understanding": "You want to decide whether to build memory next.",
    "challenged_assumption": "I think you're assuming memory is the bottleneck.",
    "current_thinking": "My current intuition is that validation matters more.",
    "biggest_uncertainty": "Whether any user has actually asked for memory.",
    "question": "Has a single user actually asked for memory?",
    "recommendation": "",
}

_RECOMMENDATION_TURN = {
    "understanding": "You have your answer now.",
    "challenged_assumption": "You assumed users want memory.",
    "current_thinking": "Given no user asked, validation comes first.",
    "biggest_uncertainty": "",
    "question": "",
    "recommendation": "Do not build memory yet; validate demand first.",
    "confidence_level": "Medium",
    "confidence_reasons": [
        {"supports": True, "text": "You have a working prototype."},
        {"supports": False, "text": "No user has asked for memory."},
    ],
    "counterargument": "A power user might churn without memory.",
    "unknowns": ["retention drivers"],
    "what_would_change_my_mind": ["several users request memory"],
    "evidence": ["No user has requested memory."],
    "experiments": [
        {
            "goal": "Learn whether founders voluntarily return.",
            "duration": "3 days",
            "success": "5 founders complete two conversations.",
            "failure": "Nobody returns.",
        }
    ],
}


def test_reasons_immediately_with_one_question() -> None:
    llm = FakeLLM(_DIALOGUE_TURN)

    result = think("I think memory is the next thing to build.", workspace=_workspace(), llm=llm)

    assert llm.calls == 1  # one turn, not an interview
    assert result.understanding
    assert result.challenged_assumption  # challenge is present up front
    assert result.current_thinking  # it exposes its lean instead of only asking
    assert result.question == "Has a single user actually asked for memory?"
    assert result.recommendation == ""  # it engages without committing yet
    assert not hasattr(result, "needs_clarification")  # no clarification gate
    assert not hasattr(result, "clarifying_questions")


def test_recommends_when_conversation_supports_it() -> None:
    llm = FakeLLM(_RECOMMENDATION_TURN)

    result = think("So what should we do?", workspace=_workspace(), llm=llm)

    assert result.recommendation.startswith("Do not build memory")
    assert result.confidence_level == "Medium"
    supports = [r.supports for r in result.confidence_reasons]
    assert True in supports and False in supports
    assert result.experiments and result.experiments[0].duration == "3 days"
    assert result.counterargument


def test_confidence_and_experiments_gated_on_recommendation() -> None:
    # A dialogue turn with no recommendation must not surface confidence/experiments,
    # even if the model returned them.
    turn = {**_DIALOGUE_TURN, "confidence_level": "High", "experiments": [{"goal": "x"}]}
    llm = FakeLLM(turn)

    result = think("thinking out loud", workspace=_workspace(), llm=llm)

    assert result.recommendation == ""
    assert result.confidence_level == ""
    assert result.confidence_reasons == ()
    assert result.experiments == ()


def test_reasoning_uses_only_conversation_and_context() -> None:
    # Contamination guard: think() takes no external research capability, and the
    # only inputs to the model are the founder message, the history, and context.
    assert "research" not in inspect.signature(think).parameters

    llm = FakeLLM(_DIALOGUE_TURN)
    think("Should I quit my job?", workspace=_workspace(), llm=llm, history=("You: earlier",))

    system_prompt = llm.messages[0].content
    user_prompt = llm.messages[1].content
    assert "Ground your reasoning ONLY" in system_prompt
    assert "Never introduce companies, projects" in system_prompt
    assert "Should I quit my job?" in user_prompt
    assert "You: earlier" in user_prompt


def test_beliefs_are_injected_as_priors() -> None:
    llm = FakeLLM(_DIALOGUE_TURN)

    think(
        "Should we build memory?",
        workspace=_workspace(),
        llm=llm,
        beliefs=("[medium] Memory is the next bottleneck",),
    )

    user_prompt = llm.messages[1].content
    assert "Relevant beliefs" in user_prompt
    assert "Memory is the next bottleneck" in user_prompt
    assert "you may disagree" in user_prompt  # beliefs are priors, not facts


def test_no_beliefs_means_no_beliefs_block() -> None:
    llm = FakeLLM(_DIALOGUE_TURN)

    think("Should we build memory?", workspace=_workspace(), llm=llm)

    assert "Relevant beliefs" not in llm.messages[1].content


def test_render_dialogue_turn_smoke() -> None:
    console = Console(file=StringIO())

    render_thinking(think("q", workspace=_workspace(), llm=FakeLLM(_DIALOGUE_TURN)), console)

    output = console.file.getvalue()
    assert "Has a single user actually asked for memory?" in output


def test_render_recommendation_smoke() -> None:
    console = Console(file=StringIO())
    result = ThinkingResult(
        problem="p",
        understanding="You want X.",
        recommendation="Do X",
        confidence_level="Medium",
        confidence_reasons=(
            ConfidenceReason(supports=True, text="prototype"),
            ConfidenceReason(supports=False, text="no validation"),
        ),
        counterargument="Demand may not exist",
        experiments=(Experiment(goal="g", duration="3 days", success="s", failure="f"),),
    )

    render_thinking(result, console)

    output = console.file.getvalue()
    assert "Do X" in output
    assert "Medium" in output
    assert "Experiments" in output


def test_build_llm_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LLMUnavailableError):
        build_llm(LLMConfig())


def test_build_llm_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    llm = build_llm(LLMConfig())
    assert hasattr(llm, "complete_json")
