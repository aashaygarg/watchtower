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
