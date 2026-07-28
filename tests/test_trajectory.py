"""Tests for the ephemeral trajectory writer and its opt-in use by the REPL."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from watchtower.adapters.persistence.trajectory import (
    TRAJECTORY_SCHEMA,
    save_trajectory,
    serialize_trajectory,
)
from watchtower.domain.messages import Message
from watchtower.session import run
from watchtower.startup.models import Startup, StartupId, StartupWorkspace


def test_serialize_trajectory_is_versioned() -> None:
    payload = serialize_trajectory(["You: hi", "Watchtower: hello"])
    assert payload == {
        "schema": TRAJECTORY_SCHEMA,
        "turns": ["You: hi", "Watchtower: hello"],
    }


def test_save_trajectory_writes_versioned_json(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "trajectory.json"
    save_trajectory(["You: hi"], path)

    assert path.exists()  # parent directory was created
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema"] == TRAJECTORY_SCHEMA
    assert data["turns"] == ["You: hi"]


class _FakeOracle:
    def complete(self, messages: Sequence[Message]) -> str:
        return ""

    def complete_json(self, messages: Sequence[Message]) -> dict[str, Any]:
        return {}


def _workspace(root: Path) -> StartupWorkspace:
    return StartupWorkspace(
        root=root,
        startup=Startup(id=StartupId("acme"), name="Acme"),
        vision="",
    )


def test_repl_writes_trajectory_when_path_given(tmp_path: Path) -> None:
    inputs = iter(["Should we raise now?", "exit"])
    path = tmp_path / "trajectory.json"

    history = run(
        workspace=_workspace(tmp_path),
        oracle=_FakeOracle(),
        beliefs=[],
        read_input=lambda: next(inputs),
        render_turn=lambda result: None,
        trajectory_path=path,
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["turns"] == history
    assert any("Should we raise now?" in turn for turn in data["turns"])


def test_repl_writes_no_trajectory_by_default(tmp_path: Path) -> None:
    inputs = iter(["Should we raise now?", "exit"])

    run(
        workspace=_workspace(tmp_path),
        oracle=_FakeOracle(),
        beliefs=[],
        read_input=lambda: next(inputs),
        render_turn=lambda result: None,
    )

    assert not (tmp_path / "trajectory.json").exists()  # unchanged default behavior
