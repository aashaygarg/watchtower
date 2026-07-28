"""Ollama provider adapter (local Ollama server)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from watchtower.adapters.providers._json import _parse_json
from watchtower.adapters.providers._retry import DEFAULT_ATTEMPTS, call_with_retry
from watchtower.adapters.providers.errors import LLMUnavailableError
from watchtower.domain.judgment import degraded_payload
from watchtower.domain.messages import Message


class OllamaLLM:
    """Oracle backed by a local Ollama server."""

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
        return call_with_retry(
            lambda: _parse_json(self._generate(messages, as_json=True)),
            attempts=DEFAULT_ATTEMPTS,
            default_factory=degraded_payload,
        )


def _dig(obj: Any, *keys: str) -> Any:
    for key in keys:
        obj = obj[key] if isinstance(obj, dict) else getattr(obj, key)
    return obj
