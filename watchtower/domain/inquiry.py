"""Inquiry: conversational state for a single clarification.

An :class:`Inquiry` tracks one clarification question across turns so that a
conversation converges. Once an inquiry is answered it is never asked again, and
an unanswered one may be rephrased at most once before it is abandoned.

An inquiry is neither a belief nor a decision: it is transient state that lives
only within a conversation and is never persisted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class InquiryStatus(StrEnum):
    """Lifecycle state of an inquiry."""

    OPEN = "open"
    ANSWERED = "answered"
    ABANDONED = "abandoned"


@dataclass(frozen=True, slots=True, kw_only=True)
class Inquiry:
    """One clarification question and whether it has been resolved.

    Attributes:
        id: Stable unique identifier within the conversation.
        original_question: The question as it was asked.
        uncertainty_being_resolved: The uncertainty the question is meant to close.
        asked_at: When it was last asked.
        status: Whether it is open, answered, or abandoned.
        founder_answer: The founder's answer, once it is resolved.
        resolution_summary: A short note on how it was resolved.
        times_asked: How many times it has been asked (original plus rephrasings).
    """

    id: str
    original_question: str
    uncertainty_being_resolved: str
    asked_at: datetime | None = None
    status: InquiryStatus = InquiryStatus.OPEN
    founder_answer: str = ""
    resolution_summary: str = ""
    times_asked: int = 1
