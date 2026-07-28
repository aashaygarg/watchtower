"""Errors raised while constructing or driving a provider adapter."""

from __future__ import annotations


class LLMError(RuntimeError):
    """Base error for the provider layer."""


class LLMUnavailableError(LLMError):
    """Raised when no provider can be constructed (missing key, package, or provider)."""
