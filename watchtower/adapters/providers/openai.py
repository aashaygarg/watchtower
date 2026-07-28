"""OpenAI-compatible provider adapter (OpenAI, vLLM, and similar endpoints)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from watchtower.adapters.providers._json import _parse_json
from watchtower.adapters.providers._retry import DEFAULT_ATTEMPTS, call_with_retry
from watchtower.adapters.providers.errors import LLMUnavailableError
from watchtower.domain.judgment import degraded_payload
from watchtower.domain.messages import Message


class OpenAICompatibleLLM:
    """Oracle backed by any OpenAI-compatible endpoint (OpenAI, vLLM, etc.)."""

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
        return call_with_retry(
            lambda: _parse_json(self._generate(messages, as_json=True)),
            attempts=DEFAULT_ATTEMPTS,
            default_factory=degraded_payload,
        )
