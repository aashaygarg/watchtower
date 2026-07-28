"""Parsing a provider's raw completion into a JSON object."""

from __future__ import annotations

import json
from typing import Any

from watchtower.adapters.providers.errors import LLMError


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
