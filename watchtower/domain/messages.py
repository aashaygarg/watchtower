"""Message domain model: a single chat message and its constructors.

A :class:`Message` is the unit the reasoning kernel hands to the oracle - a role
and its content. Like the rest of the domain it is pure, immutable data with no
dependency on any provider, SDK, or framework: only the standard library.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Message:
    """A single chat message."""

    role: str
    content: str


def system(content: str) -> Message:
    """Build a system message."""
    return Message(role="system", content=content)


def user(content: str) -> Message:
    """Build a user message."""
    return Message(role="user", content=content)
