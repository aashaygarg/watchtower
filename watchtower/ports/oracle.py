"""The oracle port: the seam through which the kernel reaches a language model.

The reasoning kernel depends only on this :class:`Oracle` protocol - never on a
concrete client, provider, or SDK. Any object that turns a sequence of messages
into a completion (or a JSON object) satisfies it. Concrete adapters live
outside the kernel and are wired in at the composition root.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from watchtower.domain.messages import Message


class Oracle(Protocol):
    """Port for a chat language model that produces typed judgments."""

    def complete(self, messages: Sequence[Message]) -> str:
        """Return the model's free-text completion for ``messages``."""
        ...

    def complete_json(self, messages: Sequence[Message]) -> dict[str, Any]:
        """Return the model's JSON-object completion for ``messages``."""
        ...
