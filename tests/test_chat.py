"""Tests for the conversational `chat` command."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner
from watchtower.interface import app

runner = CliRunner()


def _write_vision(root: Path) -> None:
    (root / "vision.md").write_text("# HealthOS\n\nMake health simple.\n", encoding="utf-8")


def test_chat_requires_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_vision(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = runner.invoke(app, ["chat", "--path", str(tmp_path)])

    assert result.exit_code == 1
    assert "can't reason yet" in result.stdout


def test_chat_exits_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_vision(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-used")

    result = runner.invoke(app, ["chat", "--path", str(tmp_path)], input="exit\n")

    assert result.exit_code == 0
    assert "HealthOS" in result.stdout


def test_chat_missing_workspace(tmp_path: Path) -> None:
    result = runner.invoke(app, ["chat", "--path", str(tmp_path / "nope")])

    assert result.exit_code == 1
