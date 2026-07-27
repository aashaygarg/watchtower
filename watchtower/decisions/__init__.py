"""Public API for Watchtower's decision engine.

Decisions record what the founder actually chose to do, why, and whether it
turned out to be correct. This subsystem is independent of the belief engine
(beliefs may support decisions, but decisions never mutate beliefs) and of
embeddings, retrieval, and agents.
"""

from watchtower.decisions.engine import (
    capture_decisions,
    mark_completed,
    record_decisions,
    record_review,
    review_decision,
)
from watchtower.decisions.store import DecisionStore, JsonDecisionStore
from watchtower.domain.decisions import (
    Decision,
    DecisionEvent,
    DecisionEventKind,
    DecisionReview,
    DecisionStatus,
)

__all__ = [
    "Decision",
    "DecisionEvent",
    "DecisionEventKind",
    "DecisionReview",
    "DecisionStatus",
    "DecisionStore",
    "JsonDecisionStore",
    "capture_decisions",
    "mark_completed",
    "record_decisions",
    "record_review",
    "review_decision",
]
