"""Anthropic provider adapter (Anthropic Messages API)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from watchtower.adapters.providers._json import _parse_json
from watchtower.adapters.providers._retry import DEFAULT_ATTEMPTS, call_with_retry
from watchtower.adapters.providers.errors import LLMUnavailableError
from watchtower.domain.judgment import degraded_payload
from watchtower.domain.messages import Message


class AnthropicLLM:
    """Oracle backed by the Anthropic Messages API."""

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
        return call_with_retry(
            lambda: _parse_json(self._generate(messages, as_json=True)),
            attempts=DEFAULT_ATTEMPTS,
            default_factory=degraded_payload,
        )


def _split_system(messages: Sequence[Message]) -> tuple[str, list[Message]]:
    system_text = "\n\n".join(m.content for m in messages if m.role == "system")
    chat = [m for m in messages if m.role != "system"]
    return system_text, chat
