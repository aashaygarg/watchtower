"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest
from watchtower.config import Config, LLMConfig, load_config


def test_load_config_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WATCHTOWER_CONFIG", raising=False)

    config = load_config()

    assert isinstance(config, Config)
    assert isinstance(config.llm, LLMConfig)
    assert config.llm.model == "gpt-4o-mini"


def test_load_config_reads_yaml(tmp_path: Path) -> None:
    config_file = tmp_path / "watchtower.yaml"
    config_file.write_text("llm:\n  model: my-model\n  temperature: 0.7\n")

    config = load_config(config_file)

    assert config.llm.model == "my-model"
    assert config.llm.temperature == 0.7


def test_load_config_discovers_from_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Config at the project root; workspace in a subdirectory; CWD is elsewhere.
    (tmp_path / "watchtower.yaml").write_text(
        "llm:\n  provider: ollama\n  model: local-model\n", encoding="utf-8"
    )
    workspace = tmp_path / "startup"
    workspace.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.delenv("WATCHTOWER_CONFIG", raising=False)

    config = load_config(search_from=workspace)

    # Discovery is anchored on the workspace, not the current directory.
    assert config.llm.provider == "ollama"
    assert config.llm.model == "local-model"


def test_load_config_ignores_cwd_without_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A watchtower.yaml in the CWD is not silently auto-loaded; that CWD-relative
    # pickup was the original provider-config bug.
    (tmp_path / "watchtower.yaml").write_text("llm:\n  provider: ollama\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WATCHTOWER_CONFIG", raising=False)

    config = load_config()

    assert config.llm.provider == "openai"
