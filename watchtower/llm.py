"""Provider-agnostic LLM interface.

Cognition depends only on the :class:`LLM` protocol, never on a concrete client
or provider. Four implementations are available — :class:`OpenAICompatibleLLM`,
:class:`OllamaLLM`, :class:`AnthropicLLM`, and :class:`GeminiLLM` — and which one
is used is decided entirely by configuration via :func:`build_llm`.

Each non-core provider SDK is an optional dependency imported lazily; a missing
package or key raises :class:`LLMUnavailableError` so the caller can degrade.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from watchtower.domain.messages import Message
from watchtower.ports.oracle import Oracle

if TYPE_CHECKING:
    from watchtower.config import LLMConfig


class LLMError(RuntimeError):
    """Base error for the LLM layer."""


class LLMUnavailableError(LLMError):
    """Raised when no LLM can be constructed (missing key, package, or provider)."""


class OpenAICompatibleLLM:
    """LLM backed by any OpenAI-compatible endpoint (OpenAI, vLLM, etc.)."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - openai is a core dependency
            raise LLMUnavailableError("the openai package is not installed") from exc
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._temperature = temperature

    def _generate(self, messages: Sequence[Message], *, as_json: bool) -> str:
        extra: dict[str, Any] = {"response_format": {"type": "json_object"}} if as_json else {}
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            **extra,
        )
        return response.choices[0].message.content or ""

    def complete(self, messages: Sequence[Message]) -> str:
        return self._generate(messages, as_json=False)

    def complete_json(self, messages: Sequence[Message]) -> dict[str, Any]:
        return _parse_json(self._generate(messages, as_json=True))


class OllamaLLM:
    """LLM backed by a local Ollama server."""

    def __init__(
        self,
        *,
        model: str,
        base_url: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        try:
            from ollama import Client
        except ImportError as exc:
            raise LLMUnavailableError("the ollama package is not installed") from exc
        self._client = Client(host=base_url) if base_url else Client()
        self._model = model
        self._temperature = temperature

    def _generate(self, messages: Sequence[Message], *, as_json: bool) -> str:
        response = self._client.chat(
            model=self._model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            options={"temperature": self._temperature},
            format="json" if as_json else None,
        )
        return str(_dig(response, "message", "content"))

    def complete(self, messages: Sequence[Message]) -> str:
        return self._generate(messages, as_json=False)

    def complete_json(self, messages: Sequence[Message]) -> dict[str, Any]:
        return _parse_json(self._generate(messages, as_json=True))


class AnthropicLLM:
    """LLM backed by the Anthropic Messages API."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> None:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise LLMUnavailableError("the anthropic package is not installed") from exc
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = Anthropic(**kwargs)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def _generate(self, messages: Sequence[Message], *, as_json: bool) -> str:
        system_text, chat = _split_system(messages)
        if as_json:
            system_text = (system_text + "\nReturn only a single JSON object, no prose.").strip()
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "messages": [{"role": m.role, "content": m.content} for m in chat],
        }
        if system_text:
            kwargs["system"] = system_text
        response = self._client.messages.create(**kwargs)
        return "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )

    def complete(self, messages: Sequence[Message]) -> str:
        return self._generate(messages, as_json=False)

    def complete_json(self, messages: Sequence[Message]) -> dict[str, Any]:
        return _parse_json(self._generate(messages, as_json=True))


class GeminiLLM:
    """LLM backed by the Google Gemini API."""

    def __init__(self, *, model: str, api_key: str, temperature: float = 0.0) -> None:
        try:
            from google import genai
        except ImportError as exc:
            raise LLMUnavailableError("the google-genai package is not installed") from exc
        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._temperature = temperature

    def _generate(self, messages: Sequence[Message], *, as_json: bool) -> str:
        from google.genai import types

        system_text, chat = _split_system(messages)
        config = types.GenerateContentConfig(
            temperature=self._temperature,
            system_instruction=system_text or None,
            response_mime_type="application/json" if as_json else None,
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents="\n\n".join(m.content for m in chat),
            config=config,
        )
        return response.text or ""

    def complete(self, messages: Sequence[Message]) -> str:
        return self._generate(messages, as_json=False)

    def complete_json(self, messages: Sequence[Message]) -> dict[str, Any]:
        return _parse_json(self._generate(messages, as_json=True))


_DEFAULT_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "openai_compatible": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def build_llm(config: LLMConfig) -> Oracle:
    """Construct an :class:`LLM` from configuration.

    The provider is chosen by ``config.provider``. Nothing above this function
    knows which implementation is returned.

    Raises:
        LLMUnavailableError: For an unknown provider, a missing API key, or a
            missing provider package.
    """
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


def _split_system(messages: Sequence[Message]) -> tuple[str, list[Message]]:
    system_text = "\n\n".join(m.content for m in messages if m.role == "system")
    chat = [m for m in messages if m.role != "system"]
    return system_text, chat


def _dig(obj: Any, *keys: str) -> Any:
    for key in keys:
        obj = obj[key] if isinstance(obj, dict) else getattr(obj, key)
    return obj


def _parse_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise LLMError(f"model did not return valid JSON: {content[:200]!r}") from None
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"model did not return valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("model JSON response was not an object")
    return data
