"""Configuration loading for Watchtower.

Settings are read from a YAML file and layered with environment variables
loaded via ``python-dotenv``. Business logic is intentionally omitted during
scaffolding — this module only defines the shape of configuration and how it
is loaded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

DEFAULT_CONFIG_PATH = Path("watchtower.yaml")


@dataclass(slots=True)
class LLMConfig:
    """Settings for the OpenAI-compatible LLM interface."""

    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    api_key_env: str = "OPENAI_API_KEY"
    base_url: str | None = None


@dataclass(slots=True)
class Config:
    """Top-level Watchtower configuration."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    raw: dict[str, Any] = field(default_factory=dict)


def load_config(path: str | Path | None = None) -> Config:
    """Load configuration from YAML and environment variables.

    Args:
        path: Optional explicit path to the YAML config file. Falls back to the
            ``WATCHTOWER_CONFIG`` environment variable and then to
            ``watchtower.yaml`` in the current directory.

    Returns:
        A populated :class:`Config` instance.
    """
    load_dotenv()
    config_path = Path(path or os.getenv("WATCHTOWER_CONFIG", DEFAULT_CONFIG_PATH))

    raw: dict[str, Any] = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text()) or {}

    llm_raw = raw.get("llm", {})
    known = {k: v for k, v in llm_raw.items() if k in LLMConfig.__dataclass_fields__}
    return Config(llm=LLMConfig(**known), raw=raw)
