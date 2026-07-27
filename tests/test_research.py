"""Tests for the research services: placeholder, GPT-Researcher, degradation."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from watchtower.startup.workspace import StartupWorkspace, load_workspace
from watchtower.tools.research import (
    GPTResearcherRunner,
    GPTResearchService,
    PlaceholderResearchService,
    RawResearch,
    ResearchBriefing,
    ResearchSource,
    ResearchUnavailableError,
    SourceKind,
    build_research_query,
)


def _workspace(root: Path) -> StartupWorkspace:
    (root / "vision.md").write_text("# Acme\n\nAcme makes X for Y.\n", encoding="utf-8")
    (root / "goals.yaml").write_text(
        "goals:\n  - id: g1\n    title: Reach PMF\n    status: active\n", encoding="utf-8"
    )
    (root / "strategies.yaml").write_text(
        "strategies:\n  - id: s1\n    goal_id: g1\n    title: Land SMB beachhead\n",
        encoding="utf-8",
    )
    (root / "hypotheses.yaml").write_text(
        "hypotheses:\n  - id: h1\n    statement: Users want X\n    confidence: 0.3\n",
        encoding="utf-8",
    )
    return load_workspace(root)


class _StubRunner:
    """A ResearchRunner that returns canned raw research and records queries."""

    def __init__(self, raw: RawResearch) -> None:
        self._raw = raw
        self.queries: list[str] = []

    def run(self, query: str) -> RawResearch:
        self.queries.append(query)
        return self._raw


class _FailingRunner:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def run(self, query: str) -> RawResearch:
        raise self._exc


_STRUCTURED = RawResearch(
    summary="The market is shifting toward X.",
    sources=(
        ResearchSource(
            title="Rival raises Series B",
            url="https://crunchbase.com/rival",
            snippet="A competitor raised funding.",
            kind=SourceKind.COMPETITOR,
        ),
        ResearchSource(
            title="RCT on X adoption",
            url="https://arxiv.org/abs/1234",
            snippet="A study on X.",
            kind=SourceKind.PAPER,
        ),
        ResearchSource(
            title="Regulation shifts",
            url="https://news.example/reg",
            snippet="New rules take effect.",
            kind=SourceKind.MARKET,
        ),
    ),
    confidence=0.7,
)


def test_placeholder_still_available(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    briefing = PlaceholderResearchService().investigate(workspace)

    assert briefing.is_placeholder is True
    assert len(briefing.findings) == len(workspace.hypotheses)


def test_query_uses_workspace_context(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    query = build_research_query(workspace)

    assert "Acme makes X for Y." in query  # mission from vision.md
    assert "Reach PMF" in query  # goal
    assert "Land SMB beachhead" in query  # strategy
    assert "Users want X" in query  # hypothesis


def test_gpt_service_structures_output(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    runner = _StubRunner(_STRUCTURED)
    service = GPTResearchService(runner=runner, fallback=PlaceholderResearchService())

    briefing = service.investigate(workspace)

    assert isinstance(briefing, ResearchBriefing)
    assert briefing.is_placeholder is False
    assert briefing.confidence == 0.7
    assert len(briefing.competitor_updates) == 1
    assert briefing.competitor_updates[0].name == "Rival raises Series B"
    assert len(briefing.scientific_papers) == 1
    assert len(briefing.market_changes) == 1
    assert len(briefing.new_evidence) == 3
    assert briefing.findings  # a summary finding is produced
    assert runner.queries and "Users want X" in runner.queries[0]


def test_gpt_service_degrades_when_unavailable(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    service = GPTResearchService(
        runner=_FailingRunner(ResearchUnavailableError("no package")),
        fallback=PlaceholderResearchService(),
    )

    briefing = service.investigate(workspace)

    assert briefing.is_placeholder is True
    assert len(briefing.findings) == len(workspace.hypotheses)


def test_gpt_service_degrades_on_unexpected_error(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    service = GPTResearchService(runner=_FailingRunner(ValueError("boom")))

    briefing = service.investigate(workspace)

    # Falls back to the default placeholder even on an unexpected error.
    assert briefing.is_placeholder is True


def test_real_runner_unavailable_without_package(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    if importlib.util.find_spec("gpt_researcher") is not None:
        pytest.skip("gpt-researcher is installed; skipping unavailable-path test")

    with pytest.raises(ResearchUnavailableError):
        GPTResearcherRunner().run(build_research_query(workspace))
