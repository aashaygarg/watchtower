"""Google Gemini provider adapter."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from watchtower.adapters.providers._json import _parse_json
from watchtower.adapters.providers._retry import DEFAULT_ATTEMPTS, call_with_retry
from watchtower.adapters.providers.errors import LLMUnavailableError
from watchtower.domain.judgment import degraded_payload
from watchtower.domain.messages import Message


class GeminiLLM:
    """Oracle backed by the Google Gemini API."""

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
        return call_with_retry(
            lambda: _parse_json(self._generate(messages, as_json=True)),
            attempts=DEFAULT_ATTEMPTS,
            default_factory=degraded_payload,
        )


def _split_system(messages: Sequence[Message]) -> tuple[str, list[Message]]:
    system_text = "\n\n".join(m.content for m in messages if m.role == "system")
    chat = [m for m in messages if m.role != "system"]
    return system_text, chat
