"""Tests for the core thinking capability and the LLM seam."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from watchtower.cognition import ThinkingResult, think
from watchtower.config import LLMConfig
from watchtower.llm import LLMUnavailableError, Message, build_llm
from watchtower.startup.models import Startup, StartupId
from watchtower.startup.workspace import StartupWorkspace
from watchtower.tools.research import ResearchBriefing, ResearchFinding


def _workspace() -> StartupWorkspace:
    return StartupWorkspace(
        root=Path("."),
        startup=Startup(id=StartupId("healthos"), name="HealthOS", mission="Make health simple."),
        vision="",
    )


class FakeLLM:
    """Routes JSON responses by the system prompt; models evidence sufficiency."""

    def __init__(self, *, sufficient_without_research: bool) -> None:
        self.sufficient = sufficient_without_research
        self.redteam_calls = 0

    def complete(self, messages: Sequence[Message]) -> str:
        return "ok"

    def complete_json(self, messages: Sequence[Message]) -> dict[str, Any]:
        instruction = messages[0].content
        prompt = messages[1].content
        if "competing hypotheses" in instruction:
            return {"restatement": "r", "success_criteria": "s", "hypotheses": ["H1", "H2"]}
        if "red team" in instruction:
            self.redteam_calls += 1
            has_evidence = "(none yet)" not in prompt
            sufficient = self.sufficient or has_evidence
            return {
                "red_team": ["H1 assumes demand that is unproven"],
                "internal_evidence": ["internal reasoning point"],
                "open_questions": [] if sufficient else ["Is there real demand for X?"],
                "evidence_sufficient": sufficient,
            }
        if "final recommendation" in instruction:
            return {
                "recommendation": "Pursue H1",
                "confidence": 0.8,
                "unknowns": ["pricing tolerance"],
                "what_would_change_my_mind": ["evidence of low willingness to pay"],
            }
        return {}


class FakeResearch:
    def __init__(self) -> None:
        self.calls = 0

    def investigate(self, workspace: StartupWorkspace) -> ResearchBriefing:
        self.calls += 1
        return ResearchBriefing(
            findings=(ResearchFinding(topic="demand", summary="external finding on demand"),),
            is_placeholder=False,
        )


def test_think_stops_when_evidence_sufficient() -> None:
    llm = FakeLLM(sufficient_without_research=True)
    research = FakeResearch()

    result = think("Should we build X?", workspace=_workspace(), llm=llm, research=research)

    assert isinstance(result, ThinkingResult)
    assert research.calls == 0  # minimum thinking: no external research needed
    assert result.used_external_research is False
    assert result.recommendation == "Pursue H1"
    assert result.confidence == 0.8
    assert result.hypotheses == ("H1", "H2")
    assert result.red_team  # red team is first-class
    assert result.unknowns == ("pricing tolerance",)
    assert result.what_would_change_my_mind == ("evidence of low willingness to pay",)


def test_think_escalates_when_evidence_insufficient() -> None:
    llm = FakeLLM(sufficient_without_research=False)
    research = FakeResearch()

    result = think("Should we build X?", workspace=_workspace(), llm=llm, research=research)

    # The evidence-sufficiency gate (not confidence) triggered external research.
    assert research.calls == 1
    assert result.used_external_research is True
    assert llm.redteam_calls == 2  # re-assessed after gathering evidence
    assert any("external finding" in item for item in result.evidence)
    assert result.confidence == 0.8  # confidence is the outcome, still produced


def test_build_llm_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LLMUnavailableError):
        build_llm(LLMConfig())


def test_build_llm_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")
    llm = build_llm(LLMConfig())
    assert hasattr(llm, "complete_json")
