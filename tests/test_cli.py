"""Tests for the Watchtower CLI."""

from __future__ import annotations

from typer.testing import CliRunner
from watchtower import __version__
from watchtower.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_shows_description() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Watchtower" in result.stdout
