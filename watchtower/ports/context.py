"""The context port: the seam for measuring the context sent to the oracle.

A :class:`ContextProvider` measures how much of a conversation is handed to the
oracle on a turn, so the kernel can keep within a model's budget without knowing
about any tokenizer. Concrete providers (for example a token counter) live
outside the kernel and are wired in at the composition root.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from watchtower.domain.messages import Message


class ContextProvider(Protocol):
    """Port for measuring the context handed to the oracle."""

    def count_tokens(self, messages: Sequence[Message]) -> int:
        """Return the number of tokens ``messages`` occupy."""
        ...
