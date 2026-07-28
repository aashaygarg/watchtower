"""Loading a founder's startup workspace from local files.

A *startup workspace* is a directory on disk holding the founder's living
context. ``vision.md`` establishes the startup's identity and is required; the
YAML files each hold a list of one entity type and are all optional. A missing
or empty YAML file simply yields an empty collection, so a founder can grow the
workspace over time and every ``watchtower`` command keeps working.

* ``vision.md``        - free-form narrative. The first heading is treated as the
                         startup name and the first paragraph as its mission.
* ``goals.yaml``       - a list of goals (:class:`~watchtower.startup.models.Goal`).
* ``strategies.yaml``  - a list of strategies (:class:`~watchtower.startup.models.Strategy`).
* ``hypotheses.yaml``  - a list of hypotheses (:class:`~watchtower.startup.models.Hypothesis`).
* ``experiments.yaml`` - a list of experiments (:class:`~watchtower.startup.models.Experiment`).
* ``decisions.yaml``   - a list of decisions (:class:`~watchtower.startup.models.Decision`).

This module turns those files into the pure domain objects defined in
:mod:`watchtower.startup.models`. It performs only file reading, YAML parsing,
and boundary validation. It has no LLM, network, or orchestration dependencies,
so it can back any future front end unchanged.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from watchtower.startup.enums import (
    DecisionStatus,
    ExperimentStatus,
    GoalStatus,
    HypothesisStatus,
    StrategyStatus,
)
from watchtower.startup.models import (
    Decision,
    DecisionId,
    Experiment,
    ExperimentId,
    Goal,
    GoalId,
    Hypothesis,
    HypothesisId,
    Startup,
    StartupId,
    StartupWorkspace,
    Strategy,
    StrategyId,
)


class WorkspaceError(Exception):
    """Raised when a startup workspace cannot be found, read, or parsed."""


def load_workspace(path: str | Path) -> StartupWorkspace:
    """Load a startup workspace from ``path``.

    Args:
        path: Directory containing at least ``vision.md``. ``goals.yaml``,
            ``strategies.yaml``, ``hypotheses.yaml``, ``experiments.yaml``, and
            ``decisions.yaml`` are optional; missing or empty files yield empty
            collections.

    Returns:
        A fully populated :class:`StartupWorkspace`.

    Raises:
        WorkspaceError: If the directory or ``vision.md`` is missing, or if any
            present YAML file is malformed.
    """
    root = Path(path)
    if not root.is_dir():
        raise WorkspaceError(f"startup workspace directory not found: {root}")

    vision = _read_required(root / "vision.md")
    goals_text = _read_optional(root / "goals.yaml")
    strategies_text = _read_optional(root / "strategies.yaml")
    hypotheses_text = _read_optional(root / "hypotheses.yaml")
    experiments_text = _read_optional(root / "experiments.yaml")
    decisions_text = _read_optional(root / "decisions.yaml")

    name, mission = _extract_name_and_mission(vision, fallback_name=root.resolve().name)
    startup = Startup(id=StartupId(_slugify(name)), name=name, mission=mission)

    return StartupWorkspace(
        root=root,
        startup=startup,
        vision=vision,
        goals=_parse_goals(_safe_yaml(goals_text, "goals.yaml"), startup.id),
        strategies=_parse_strategies(_safe_yaml(strategies_text, "strategies.yaml")),
        hypotheses=_parse_hypotheses(_safe_yaml(hypotheses_text, "hypotheses.yaml")),
        experiments=_parse_experiments(_safe_yaml(experiments_text, "experiments.yaml")),
        decisions=_parse_decisions(_safe_yaml(decisions_text, "decisions.yaml")),
    )


# A pluggable loader: any callable with this shape can be injected wherever a
# workspace needs to be produced, making the file-backed loader swappable.
WorkspaceLoader = Callable[[str | Path], StartupWorkspace]


def _read_required(path: Path) -> str:
    if not path.is_file():
        raise WorkspaceError(f"missing required file: {path.name} (expected in the workspace)")
    return path.read_text(encoding="utf-8")


def _read_optional(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _safe_yaml(text: str, filename: str) -> Any:
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise WorkspaceError(f"could not parse {filename}: {exc}") from exc


def _extract_name_and_mission(text: str, *, fallback_name: str) -> tuple[str, str]:
    name: str | None = None
    mission_lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            if name is None:
                name = line.lstrip("#").strip()
            continue
        if not line:
            if mission_lines:
                break  # end of the first paragraph
            continue
        mission_lines.append(line)
    return (name or fallback_name), " ".join(mission_lines)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "startup"


def _entries(data: Any, key: str) -> list[Any]:
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        section = data.get(key, [])
        if section is None:
            return []
        if not isinstance(section, list):
            raise WorkspaceError(f"'{key}' must be a list")
        return section
    raise WorkspaceError(f"unexpected YAML structure for '{key}'")


def _require(entry: Any, field: str, kind: str) -> Any:
    try:
        return entry[field]
    except (KeyError, TypeError) as exc:
        raise WorkspaceError(f"{kind} entry is missing required field '{field}'") from exc


def _parse_enum(enum_cls: type[Enum], value: Any, default: Enum, kind: str) -> Any:
    if value is None:
        return default
    try:
        return enum_cls(str(value))
    except ValueError as exc:
        valid = ", ".join(str(member.value) for member in enum_cls)
        raise WorkspaceError(f"invalid {kind} status '{value}'; expected one of: {valid}") from exc


def _parse_confidence(value: Any) -> float:
    if value is None:
        return 0.5
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise WorkspaceError(f"invalid confidence value '{value}'; expected a number") from exc


def _parse_tags(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(str(tag) for tag in value)


def _parse_goals(data: Any, startup_id: StartupId) -> tuple[Goal, ...]:
    goals: list[Goal] = []
    for entry in _entries(data, "goals"):
        goals.append(
            Goal(
                id=GoalId(str(_require(entry, "id", "goal"))),
                startup_id=startup_id,
                title=str(_require(entry, "title", "goal")),
                description=str(entry.get("description", "")),
                status=_parse_enum(GoalStatus, entry.get("status"), GoalStatus.PROPOSED, "goal"),
                target_metric=_optional_str(entry.get("target_metric")),
                target_value=_optional_str(entry.get("target_value")),
                tags=_parse_tags(entry.get("tags")),
            )
        )
    return tuple(goals)


def _parse_hypotheses(data: Any) -> tuple[Hypothesis, ...]:
    hypotheses: list[Hypothesis] = []
    for entry in _entries(data, "hypotheses"):
        hypotheses.append(
            Hypothesis(
                id=HypothesisId(str(_require(entry, "id", "hypothesis"))),
                statement=str(_require(entry, "statement", "hypothesis")),
                status=_parse_enum(
                    HypothesisStatus,
                    entry.get("status"),
                    HypothesisStatus.UNTESTED,
                    "hypothesis",
                ),
                confidence=_parse_confidence(entry.get("confidence")),
                rationale=str(entry.get("rationale", "")),
                tags=_parse_tags(entry.get("tags")),
            )
        )
    return tuple(hypotheses)


def _parse_strategies(data: Any) -> tuple[Strategy, ...]:
    strategies: list[Strategy] = []
    for entry in _entries(data, "strategies"):
        strategies.append(
            Strategy(
                id=StrategyId(str(_require(entry, "id", "strategy"))),
                goal_id=GoalId(str(_require(entry, "goal_id", "strategy"))),
                title=str(_require(entry, "title", "strategy")),
                description=str(entry.get("description", "")),
                status=_parse_enum(
                    StrategyStatus,
                    entry.get("status"),
                    StrategyStatus.PROPOSED,
                    "strategy",
                ),
                hypothesis_ids=_parse_ids(entry.get("hypothesis_ids"), HypothesisId),
                tags=_parse_tags(entry.get("tags")),
            )
        )
    return tuple(strategies)


def _parse_experiments(data: Any) -> tuple[Experiment, ...]:
    experiments: list[Experiment] = []
    for entry in _entries(data, "experiments"):
        experiments.append(
            Experiment(
                id=ExperimentId(str(_require(entry, "id", "experiment"))),
                name=str(_require(entry, "name", "experiment")),
                hypothesis_id=HypothesisId(str(_require(entry, "hypothesis_id", "experiment"))),
                description=str(entry.get("description", "")),
                status=_parse_enum(
                    ExperimentStatus,
                    entry.get("status"),
                    ExperimentStatus.DESIGNED,
                    "experiment",
                ),
                success_criteria=str(entry.get("success_criteria", "")),
                tags=_parse_tags(entry.get("tags")),
            )
        )
    return tuple(experiments)


def _parse_decisions(data: Any) -> tuple[Decision, ...]:
    decisions: list[Decision] = []
    for entry in _entries(data, "decisions"):
        decisions.append(
            Decision(
                id=DecisionId(str(_require(entry, "id", "decision"))),
                title=str(_require(entry, "title", "decision")),
                context=str(entry.get("context", "")),
                options_considered=_parse_tags(entry.get("options_considered")),
                chosen_option=str(entry.get("chosen_option", "")),
                rationale=str(entry.get("rationale", "")),
                status=_parse_enum(
                    DecisionStatus,
                    entry.get("status"),
                    DecisionStatus.PROPOSED,
                    "decision",
                ),
                reversible=bool(entry.get("reversible", True)),
                goal_id=_optional_id(entry.get("goal_id"), GoalId),
                strategy_id=_optional_id(entry.get("strategy_id"), StrategyId),
                hypothesis_id=_optional_id(entry.get("hypothesis_id"), HypothesisId),
                tags=_parse_tags(entry.get("tags")),
            )
        )
    return tuple(decisions)


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _parse_ids(value: Any, factory: Callable[[str], Any]) -> tuple[Any, ...]:
    if not value:
        return ()
    return tuple(factory(str(item)) for item in value)


def _optional_id(value: Any, factory: Callable[[str], Any]) -> Any:
    return None if value is None else factory(str(value))
