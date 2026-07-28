"""Watchtower's worldview: belief relevance selection and revision.

This is the kernel's belief engine. Relevance selection surfaces the beliefs
worth injecting into a turn; revision is the single place beliefs change, via one
LLM reasoning step over a conversation, with every change logged. No embeddings,
vector search, retrieval, or agents.
"""

from watchtower.kernel.worldview.relevance import format_for_prompt, select_relevant
from watchtower.kernel.worldview.revision import apply_updates, update_beliefs

__all__ = [
    "apply_updates",
    "format_for_prompt",
    "select_relevant",
    "update_beliefs",
]
