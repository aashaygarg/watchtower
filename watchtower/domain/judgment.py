"""Judgment domain model: the typed result of one turn of reasoning.

A :class:`ThinkingResult` is what the reasoning kernel produces on each turn - a
single, fully-typed judgment: the challenged assumption, the current lean, the
one open question, and, once the conversation supports it, a recommendation with
calibrated confidence. Like the rest of the domain it is pure, immutable data
that depends only on the standard library and other domain types.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from watchtower.domain.inquiry import Inquiry

#: The uncertainty stated when a turn is degraded because the oracle was unreachable.
_DEGRADED_UNCERTAINTY = (
    "Watchtower could not reach its reasoning model, so this turn is degraded: "
    "no recommendation is offered."
)


@dataclass(frozen=True, slots=True)
class ConfidenceReason:
    """One justification behind the confidence level.

    Attributes:
        supports: ``True`` if the reason raises confidence, ``False`` if it lowers it.
        text: The reason itself.
    """

    supports: bool
    text: str


@dataclass(frozen=True, slots=True)
class Experiment:
    """A concrete, time-boxed experiment that produces evidence.

    Attributes:
        goal: What the founder would learn.
        duration: How long it should take.
        success: The observable outcome that counts as success.
        failure: The observable outcome that counts as failure.
    """

    goal: str
    duration: str = ""
    success: str = ""
    failure: str = ""


@dataclass(frozen=True, slots=True)
class ThinkingResult:
    """One turn of dialogue with the founder.

    Every turn reasons out loud. Early turns typically lead with a challenged
    assumption and a single question; later turns firm up into a recommendation.

    Attributes:
        problem: The founder's latest message.
        understanding: How Watchtower currently reads what is being decided.
        challenged_assumption: The single strongest assumption, challenged.
        current_thinking: The current lean, held with honest uncertainty.
        biggest_uncertainty: The one thing Watchtower is least sure about.
        question: At most one question - the highest-value one (empty if none).
        recommendation: A recommendation, once the conversation supports one.
        confidence_level: ``Low``, ``Medium``, or ``High`` - justified, not numeric.
        confidence_reasons: The reasons for and against, behind the level.
        counterargument: The single strongest argument against the recommendation.
        unknowns: What remains genuinely uncertain.
        what_would_change_my_mind: Observations that would overturn the answer.
        evidence: The evidence actually available (never fabricated).
        experiments: One or two concrete experiments to run next.
        inquiries: The conversation's clarification state (open, answered, abandoned).
        resolved_inquiry_id: The inquiry the founder's latest message answered, if any.
    """

    problem: str
    understanding: str = ""
    challenged_assumption: str = ""
    current_thinking: str = ""
    biggest_uncertainty: str = ""
    question: str = ""
    recommendation: str = ""
    confidence_level: str = ""
    confidence_reasons: tuple[ConfidenceReason, ...] = ()
    counterargument: str = ""
    unknowns: tuple[str, ...] = ()
    what_would_change_my_mind: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    experiments: tuple[Experiment, ...] = ()
    inquiries: tuple[Inquiry, ...] = ()
    resolved_inquiry_id: str | None = None

    @classmethod
    def degraded(cls, problem: str) -> ThinkingResult:
        """A minimal, honest judgment for a turn where the oracle was unreachable.

        It carries no recommendation and states its uncertainty plainly, so a
        provider failure degrades the turn instead of crashing the dialogue.
        """
        return cls(problem=problem, biggest_uncertainty=_DEGRADED_UNCERTAINTY)


def degraded_payload() -> dict[str, Any]:
    """The JSON an oracle yields on total failure, so its callers degrade gracefully.

    Parsed by the reasoning kernel it reconstructs :meth:`ThinkingResult.degraded`;
    the belief- and decision-engines simply find nothing to act on.
    """
    return {"biggest_uncertainty": _DEGRADED_UNCERTAINTY}
