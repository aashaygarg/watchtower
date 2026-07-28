"""Watchtower's core thinking capability - a dialogue engine.

:func:`think` reasons the way an experienced co-founder does in a live
conversation: it engages immediately instead of demanding perfect information
first. Every turn it states its current understanding, challenges the single
strongest assumption in what the founder said, shares its current lean (held with
honest uncertainty), names the one thing it is least sure about, and asks at most
ONE question - the one whose answer would most change its thinking. It commits to
a recommendation only once the conversation supports it.

The goal is a dialogue, not an interview. Reasoning is grounded ONLY in the
current conversation and the explicitly loaded company context; it never pulls in
outside projects, facts, or research.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import uuid4

from watchtower.domain.inquiry import Inquiry, InquiryStatus
from watchtower.domain.judgment import ConfidenceReason, Experiment, ThinkingResult
from watchtower.domain.messages import system, user
from watchtower.kernel.inquiry import (
    _answered_block,
    _first_open,
    _open_inquiry_block,
    _replace_inquiry,
)
from watchtower.kernel.prompt import _DIALOGUE_SYSTEM
from watchtower.ports.clock import Clock
from watchtower.ports.oracle import Oracle
from watchtower.startup.models import StartupWorkspace

_CONFIDENCE_LEVELS = ("Low", "Medium", "High")
# An inquiry may be asked once and rephrased at most once before it is abandoned.
_MAX_ASKS = 2


def think(
    problem: str,
    *,
    workspace: StartupWorkspace,
    llm: Oracle,
    clock: Clock | None = None,
    history: Sequence[str] = (),
    beliefs: Sequence[str] = (),
    inquiries: Sequence[Inquiry] = (),
) -> ThinkingResult:
    """Take one turn of dialogue about ``problem``.

    Reasoning is grounded only in ``problem``, the conversation ``history``, the
    explicitly loaded ``workspace`` context, and ``beliefs`` (Watchtower's prior
    understanding, which it may disagree with) - nothing else.

    ``inquiries`` carries the conversation's clarification state so the dialogue
    converges: an answered inquiry is never asked again, and an unanswered one is
    rephrased at most once before it is abandoned. The updated state is returned
    on :attr:`ThinkingResult.inquiries`.
    """
    context = _context_summary(workspace)
    open_inquiry = _first_open(inquiries)
    answered = tuple(item for item in inquiries if item.status is InquiryStatus.ANSWERED)
    can_reask = open_inquiry is None or open_inquiry.times_asked < _MAX_ASKS

    prompt = (
        "Company context (background - use only if it is relevant to the question):\n"
        f"{context}\n\n"
        f"{_beliefs_block(beliefs)}"
        f"{_open_inquiry_block(open_inquiry, can_reask=can_reask)}"
        f"{_answered_block(answered)}"
        f"{_history_block(history)}"
        f"Founder:\n{problem}"
    )
    data = llm.complete_json([system(_DIALOGUE_SYSTEM), user(prompt)])

    updated = list(inquiries)
    resolved_id: str | None = None
    now = clock.now() if clock is not None else datetime.now()

    # 1. Resolve the open inquiry if the founder's latest message answered it.
    if open_inquiry is not None and bool(data.get("resolves_open_inquiry")):
        _replace_inquiry(
            updated,
            replace(
                open_inquiry,
                status=InquiryStatus.ANSWERED,
                founder_answer=str(data.get("founder_answer", "")).strip() or problem,
                resolution_summary=str(data.get("resolution_summary", "")).strip(),
            ),
        )
        resolved_id = open_inquiry.id
        open_inquiry = None

    # 2. Handle a question, enforcing convergence.
    question = str(data.get("question", "")).strip()
    uncertainty = str(data.get("biggest_uncertainty", "")).strip()
    if question:
        if open_inquiry is not None:
            # The open inquiry is still unresolved: this is a rephrase attempt.
            if open_inquiry.times_asked < _MAX_ASKS:
                _replace_inquiry(
                    updated,
                    replace(
                        open_inquiry,
                        original_question=question,
                        times_asked=open_inquiry.times_asked + 1,
                        asked_at=now,
                    ),
                )
            else:
                # Rephrase budget spent: abandon it and stop asking. Never loop.
                _replace_inquiry(updated, replace(open_inquiry, status=InquiryStatus.ABANDONED))
                question = ""
        else:
            updated.append(
                Inquiry(
                    id=f"inquiry-{uuid4().hex[:8]}",
                    original_question=question,
                    uncertainty_being_resolved=uncertainty or question,
                    asked_at=now,
                    status=InquiryStatus.OPEN,
                    times_asked=1,
                )
            )

    recommendation = str(data.get("recommendation", "")).strip()
    return ThinkingResult(
        problem=problem,
        understanding=str(data.get("understanding", "")).strip(),
        challenged_assumption=str(data.get("challenged_assumption", "")).strip(),
        current_thinking=str(data.get("current_thinking", "")).strip(),
        biggest_uncertainty=uncertainty,
        question=question,
        recommendation=recommendation,
        confidence_level=_confidence_level(data.get("confidence_level")) if recommendation else "",
        confidence_reasons=_parse_reasons(data.get("confidence_reasons")) if recommendation else (),
        counterargument=str(data.get("counterargument", "")).strip(),
        unknowns=_str_tuple(data.get("unknowns")),
        what_would_change_my_mind=_str_tuple(data.get("what_would_change_my_mind")),
        evidence=_str_tuple(data.get("evidence")),
        experiments=_parse_experiments(data.get("experiments")) if recommendation else (),
        inquiries=tuple(updated),
        resolved_inquiry_id=resolved_id,
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _context_summary(workspace: StartupWorkspace) -> str:
    startup = workspace.startup
    lines = [f"Startup: {startup.name}"]
    if startup.mission:
        lines.append(f"Mission: {startup.mission}")
    if workspace.goals:
        lines.append("Goals: " + "; ".join(goal.title for goal in workspace.goals))
    if workspace.strategies:
        lines.append("Strategies: " + "; ".join(item.title for item in workspace.strategies))
    if workspace.hypotheses:
        lines.append(
            "Current hypotheses: " + "; ".join(item.statement for item in workspace.hypotheses)
        )
    return "\n".join(lines)


def _history_block(history: Sequence[str]) -> str:
    if not history:
        return ""
    return "Conversation so far:\n" + "\n".join(history) + "\n\n"


def _beliefs_block(beliefs: Sequence[str]) -> str:
    if not beliefs:
        return ""
    body = "\n".join(f"- {belief}" for belief in beliefs)
    return (
        "Relevant beliefs (your prior understanding, not facts - you may disagree with them):\n"
        f"{body}\n\n"
    )


def _str_tuple(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def _confidence_level(value: Any) -> str:
    text = str(value or "").strip().capitalize()
    return text if text in _CONFIDENCE_LEVELS else "Medium"


def _parse_reasons(value: Any) -> tuple[ConfidenceReason, ...]:
    if not isinstance(value, list):
        return ()
    reasons: list[ConfidenceReason] = []
    for item in value:
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            if text:
                supports = bool(item.get("supports", True))
                reasons.append(ConfidenceReason(supports=supports, text=text))
        elif item:
            reasons.append(ConfidenceReason(supports=True, text=str(item)))
    return tuple(reasons)


def _parse_experiments(value: Any) -> tuple[Experiment, ...]:
    if not isinstance(value, list):
        return ()
    experiments: list[Experiment] = []
    for item in value:
        if isinstance(item, dict):
            goal = str(item.get("goal", "")).strip()
            if goal:
                experiments.append(
                    Experiment(
                        goal=goal,
                        duration=str(item.get("duration", "")),
                        success=str(item.get("success", "")),
                        failure=str(item.get("failure", "")),
                    )
                )
    return tuple(experiments)
