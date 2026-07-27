"""Tests for the morning vertical slice: loading, orchestration, and injection."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner
from watchtower.agents.decision import (
    DecisionRecommendation,
    PlaceholderDecisionService,
    Priority,
)
from watchtower.cli import app
from watchtower.graphs.morning import MorningReport, MorningRoutine
from watchtower.startup.enums import (
    DecisionStatus,
    ExperimentStatus,
    GoalStatus,
    HypothesisStatus,
    StrategyStatus,
)
from watchtower.startup.workspace import StartupWorkspace, WorkspaceError, load_workspace
from watchtower.tools.research import (
    PlaceholderResearchService,
    ResearchBriefing,
    ResearchFinding,
)

runner = CliRunner()


def _write_workspace(root: Path) -> None:
    (root / "vision.md").write_text("# Acme\n\nAcme makes X for Y.\n", encoding="utf-8")
    (root / "goals.yaml").write_text(
        "goals:\n"
        "  - id: g1\n"
        "    title: Reach PMF\n"
        "    status: active\n"
        "    target_metric: wau\n"
        "    target_value: '1000'\n",
        encoding="utf-8",
    )
    (root / "hypotheses.yaml").write_text(
        "hypotheses:\n"
        "  - id: h1\n"
        "    statement: Users want X\n"
        "    status: untested\n"
        "    confidence: 0.3\n"
        "  - id: h2\n"
        "    statement: Users will pay for X\n"
        "    status: testing\n"
        "    confidence: 0.6\n",
        encoding="utf-8",
    )


def test_load_workspace_parses_files(tmp_path: Path) -> None:
    _write_workspace(tmp_path)

    workspace = load_workspace(tmp_path)

    assert isinstance(workspace, StartupWorkspace)
    assert workspace.startup.name == "Acme"
    assert workspace.startup.mission == "Acme makes X for Y."
    assert len(workspace.goals) == 1
    assert workspace.goals[0].title == "Reach PMF"
    assert workspace.goals[0].status is GoalStatus.ACTIVE
    assert workspace.goals[0].startup_id == workspace.startup.id
    assert len(workspace.hypotheses) == 2
    assert workspace.hypotheses[0].status is HypothesisStatus.UNTESTED
    assert workspace.hypotheses[0].confidence == 0.3


def test_load_workspace_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceError):
        load_workspace(tmp_path / "does-not-exist")


def test_load_workspace_missing_vision(tmp_path: Path) -> None:
    # vision.md is the only required file; without it the load fails.
    with pytest.raises(WorkspaceError):
        load_workspace(tmp_path)


def test_load_workspace_optional_files_absent(tmp_path: Path) -> None:
    # A workspace with only vision.md loads with empty collections.
    (tmp_path / "vision.md").write_text("# Acme\n\nAcme makes X.\n", encoding="utf-8")

    workspace = load_workspace(tmp_path)

    assert workspace.startup.name == "Acme"
    assert workspace.goals == ()
    assert workspace.strategies == ()
    assert workspace.hypotheses == ()
    assert workspace.experiments == ()
    assert workspace.decisions == ()


def test_load_workspace_empty_files(tmp_path: Path) -> None:
    # Present-but-empty YAML files parse to empty collections, not errors.
    (tmp_path / "vision.md").write_text("# Acme\n\nAcme makes X.\n", encoding="utf-8")
    for name in ("goals", "strategies", "hypotheses", "experiments", "decisions"):
        (tmp_path / f"{name}.yaml").write_text("", encoding="utf-8")

    workspace = load_workspace(tmp_path)

    assert workspace.goals == ()
    assert workspace.strategies == ()
    assert workspace.hypotheses == ()
    assert workspace.experiments == ()
    assert workspace.decisions == ()


def test_load_workspace_parses_all_entities(tmp_path: Path) -> None:
    _write_workspace(tmp_path)
    (tmp_path / "strategies.yaml").write_text(
        "strategies:\n"
        "  - id: s1\n"
        "    goal_id: g1\n"
        "    title: Land beachhead\n"
        "    status: active\n"
        "    hypothesis_ids: [h1, h2]\n",
        encoding="utf-8",
    )
    (tmp_path / "experiments.yaml").write_text(
        "experiments:\n"
        "  - id: e1\n"
        "    name: Landing page test\n"
        "    hypothesis_id: h1\n"
        "    status: running\n"
        "    success_criteria: 5% signup rate\n",
        encoding="utf-8",
    )
    (tmp_path / "decisions.yaml").write_text(
        "decisions:\n"
        "  - id: d1\n"
        "    title: Focus on SMB\n"
        "    status: accepted\n"
        "    reversible: false\n"
        "    goal_id: g1\n"
        "    options_considered: [SMB, Enterprise]\n",
        encoding="utf-8",
    )

    workspace = load_workspace(tmp_path)

    assert len(workspace.strategies) == 1
    assert workspace.strategies[0].status is StrategyStatus.ACTIVE
    assert workspace.strategies[0].goal_id == "g1"
    assert workspace.strategies[0].hypothesis_ids == ("h1", "h2")

    assert len(workspace.experiments) == 1
    assert workspace.experiments[0].status is ExperimentStatus.RUNNING
    assert workspace.experiments[0].hypothesis_id == "h1"

    assert len(workspace.decisions) == 1
    assert workspace.decisions[0].status is DecisionStatus.ACCEPTED
    assert workspace.decisions[0].reversible is False
    assert workspace.decisions[0].options_considered == ("SMB", "Enterprise")


def test_load_workspace_invalid_status(tmp_path: Path) -> None:
    _write_workspace(tmp_path)
    (tmp_path / "goals.yaml").write_text(
        "goals:\n  - id: g1\n    title: T\n    status: bogus\n", encoding="utf-8"
    )
    with pytest.raises(WorkspaceError):
        load_workspace(tmp_path)


def test_morning_routine_end_to_end(tmp_path: Path) -> None:
    _write_workspace(tmp_path)
    routine = MorningRoutine(
        research=PlaceholderResearchService(),
        decision=PlaceholderDecisionService(),
    )

    report = routine.run(tmp_path)

    assert isinstance(report, MorningReport)
    assert len(report.research.findings) == 2
    assert report.recommendations
    # The weakest hypothesis (h1 at 0.3) should be the high-priority de-risk item.
    high = [r for r in report.recommendations if r.priority is Priority.HIGH]
    assert high and high[0].related_hypothesis_id == "h1"


def test_services_are_injectable(tmp_path: Path) -> None:
    _write_workspace(tmp_path)

    class FakeResearch:
        def investigate(self, workspace: StartupWorkspace) -> ResearchBriefing:
            return ResearchBriefing(
                findings=(ResearchFinding(topic="t", summary="s"),),
                is_placeholder=False,
            )

    class FakeDecision:
        def __init__(self) -> None:
            self.seen: ResearchBriefing | None = None

        def recommend(
            self, workspace: StartupWorkspace, research: ResearchBriefing
        ) -> tuple[DecisionRecommendation, ...]:
            self.seen = research
            return (DecisionRecommendation(title="x", rationale="y"),)

    fake_decision = FakeDecision()
    routine = MorningRoutine(research=FakeResearch(), decision=fake_decision)

    report = routine.run(tmp_path)

    assert report.research.is_placeholder is False
    assert fake_decision.seen is report.research
    assert report.recommendations[0].title == "x"


def test_loader_is_injectable(tmp_path: Path) -> None:
    _write_workspace(tmp_path)
    sentinel = load_workspace(tmp_path)
    calls: list[object] = []

    def fake_loader(path: str | Path) -> StartupWorkspace:
        calls.append(path)
        return sentinel

    routine = MorningRoutine(
        research=PlaceholderResearchService(),
        decision=PlaceholderDecisionService(),
        load=fake_loader,
    )

    report = routine.run("ignored")

    assert calls == ["ignored"]
    assert report.workspace is sentinel


def test_morning_command_renders(tmp_path: Path) -> None:
    _write_workspace(tmp_path)

    result = runner.invoke(app, ["morning", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert "Acme" in result.stdout
    assert "Recommendations" in result.stdout


def test_morning_command_missing_workspace(tmp_path: Path) -> None:
    result = runner.invoke(app, ["morning", "--path", str(tmp_path / "nope")])

    assert result.exit_code == 1


def test_bundled_sample_workspace_loads() -> None:
    sample = Path(__file__).resolve().parents[1] / "startup"
    workspace = load_workspace(sample)

    assert workspace.startup.name == "Health OS"
    # The workspace ships one placeholder example entry per file.
    assert workspace.goals
    assert workspace.strategies
    assert workspace.hypotheses
    assert workspace.experiments
    assert workspace.decisions


def test_bundled_sample_workspace_renders() -> None:
    sample = Path(__file__).resolve().parents[1] / "startup"

    result = runner.invoke(app, ["morning", "--path", str(sample)])

    assert result.exit_code == 0
    assert "Health OS" in result.stdout
