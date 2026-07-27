"""Public API for Watchtower's belief engine.

Beliefs are Watchtower's evolving worldview: conclusions distilled from
conversations, stored separately from any conversation history. This package is
independent of embeddings, vector search, retrieval, agents, and long-term
conversation memory.
"""

from watchtower.beliefs.engine import (
    apply_updates,
    format_for_prompt,
    select_relevant,
    update_beliefs,
)
from watchtower.beliefs.store import BeliefStore, JsonBeliefStore
from watchtower.domain.beliefs import (
    Belief,
    BeliefAction,
    BeliefCategory,
    BeliefConfidence,
    BeliefStatus,
    BeliefUpdate,
)

__all__ = [
    "Belief",
    "BeliefAction",
    "BeliefCategory",
    "BeliefConfidence",
    "BeliefStatus",
    "BeliefStore",
    "BeliefUpdate",
    "JsonBeliefStore",
    "apply_updates",
    "format_for_prompt",
    "select_relevant",
    "update_beliefs",
]
