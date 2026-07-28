"""Provider adapters: concrete oracles selected by configuration.

Each provider (OpenAI-compatible, Ollama, Anthropic, Gemini) is a small adapter
implementing the :class:`~watchtower.ports.oracle.Oracle` protocol.
:func:`build_oracle` selects one from configuration; nothing above this package
knows which is used.
"""

from watchtower.adapters.providers.errors import LLMError, LLMUnavailableError
from watchtower.adapters.providers.factory import build_oracle

__all__ = [
    "LLMError",
    "LLMUnavailableError",
    "build_oracle",
]
