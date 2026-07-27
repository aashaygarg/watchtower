"""OpenAI-compatible LLM interface.

A single, swappable entrypoint for constructing an OpenAI-compatible client so
the rest of the system depends on one place. Wiring is intentionally deferred
during scaffolding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from watchtower.config import LLMConfig


def build_client(config: LLMConfig) -> object:
    """Build an OpenAI-compatible client from ``config``.

    Args:
        config: The LLM configuration section.

    Returns:
        An OpenAI-compatible client instance.

    Raises:
        NotImplementedError: Always, until the client is wired up.
    """
    raise NotImplementedError("LLM client wiring is not implemented yet.")
