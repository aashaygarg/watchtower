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
    """Settings for the LLM interface.

    ``provider`` selects the implementation (openai, ollama, anthropic, gemini);
    everything else is shared. ``api_key_env`` is optional and, when unset,
    defaults to the conventional variable for the chosen provider.
    """

    provider: str = "openai"
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    api_key_env: str | None = None
    base_url: str | None = None


@dataclass(slots=True)
class Config:
    """Top-level Watchtower configuration."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    raw: dict[str, Any] = field(default_factory=dict)


def find_config_file(start: str | Path) -> Path | None:
    """Search ``start`` and its parent directories for ``watchtower.yaml``.

    ``start`` is typically the startup workspace directory; the config file
    conventionally lives at the project root above it. Returns the first match,
    or ``None`` if none is found. This makes discovery independent of the current
    working directory.
    """
    base = Path(start).resolve()
    if base.is_file():
        base = base.parent
    for directory in (base, *base.parents):
        candidate = directory / DEFAULT_CONFIG_PATH.name
        if candidate.is_file():
            return candidate
    return None


def load_config(
    path: str | Path | None = None,
    *,
    search_from: str | Path | None = None,
) -> Config:
    """Load configuration from YAML and environment variables.

    Args:
        path: Explicit path to a config file. Takes precedence over everything.
        search_from: A directory (typically the startup workspace) to search
            upward from for ``watchtower.yaml`` when no explicit ``path`` and no
            ``WATCHTOWER_CONFIG`` override are given.

    Returns:
        A populated :class:`Config` instance. Falls back to defaults only when no
        configuration file can be located.
    """
    load_dotenv()
    config_path = _resolve_config_path(path, search_from)

    raw: dict[str, Any] = {}
    if config_path is not None and config_path.is_file():
        raw = yaml.safe_load(config_path.read_text()) or {}

    llm_raw = raw.get("llm", {})
    known = {k: v for k, v in llm_raw.items() if k in LLMConfig.__dataclass_fields__}
    return Config(llm=LLMConfig(**known), raw=raw)


def _resolve_config_path(
    path: str | Path | None,
    search_from: str | Path | None,
) -> Path | None:
    if path is not None:
        return Path(path)
    override = os.getenv("WATCHTOWER_CONFIG")
    if override and Path(override).is_file():
        return Path(override)
    if search_from is not None:
        found = find_config_file(search_from)
        if found is not None:
            return found
    return Path(override) if override else None
