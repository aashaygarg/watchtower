"""Provider selection: build an oracle from configuration.

The provider is chosen entirely by ``config.provider``; nothing above this
function knows which concrete adapter is returned.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from watchtower.adapters.providers.anthropic import AnthropicLLM
from watchtower.adapters.providers.errors import LLMUnavailableError
from watchtower.adapters.providers.gemini import GeminiLLM
from watchtower.adapters.providers.limits import with_limits
from watchtower.adapters.providers.ollama import OllamaLLM
from watchtower.adapters.providers.openai import OpenAICompatibleLLM
from watchtower.ports.oracle import Oracle

if TYPE_CHECKING:
    from watchtower.config import LLMConfig

_DEFAULT_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "openai_compatible": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def build_oracle(config: LLMConfig) -> Oracle:
    """Construct an :class:`~watchtower.ports.oracle.Oracle` from configuration.

    The provider is chosen by ``config.provider``. Nothing above this function
    knows which implementation is returned. The oracle is returned behind a call
    ceiling that is a no-op unless ``WATCHTOWER_MAX_ORACLE_CALLS`` is set.

    Raises:
        LLMUnavailableError: For an unknown provider, a missing API key, or a
            missing provider package.
    """
    return with_limits(_build_provider(config))


def _build_provider(config: LLMConfig) -> Oracle:
    provider = (config.provider or "openai").lower()
    if provider in ("openai", "openai_compatible"):
        return OpenAICompatibleLLM(
            model=config.model,
            api_key=_require_key(config, provider),
            base_url=config.base_url,
            temperature=config.temperature,
        )
    if provider == "ollama":
        return OllamaLLM(
            model=config.model,
            base_url=config.base_url,
            temperature=config.temperature,
        )
    if provider == "anthropic":
        return AnthropicLLM(
            model=config.model,
            api_key=_require_key(config, provider),
            base_url=config.base_url,
            temperature=config.temperature,
        )
    if provider == "gemini":
        return GeminiLLM(
            model=config.model,
            api_key=_require_key(config, provider),
            temperature=config.temperature,
        )
    raise LLMUnavailableError(
        f"unknown LLM provider '{config.provider}'; "
        "expected one of: openai, ollama, anthropic, gemini"
    )


def _require_key(config: LLMConfig, provider: str) -> str:
    env_name = config.api_key_env or _DEFAULT_KEY_ENV.get(provider, "OPENAI_API_KEY")
    key = os.getenv(env_name)
    if not key:
        raise LLMUnavailableError(f"no API key found in ${env_name}; set it to enable reasoning")
    return key
