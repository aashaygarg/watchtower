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
from watchtower.ports.oracle import Oracle
from watchtower.startup.workspace import StartupWorkspace

_CONFIDENCE_LEVELS = ("Low", "Medium", "High")
# An inquiry may be asked once and rephrased at most once before it is abandoned.
_MAX_ASKS = 2


def think(
    problem: str,
    *,
    workspace: StartupWorkspace,
    llm: Oracle,
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
    now = datetime.now()

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
# Reasoning prompt
# --------------------------------------------------------------------------- #

_DIALOGUE_SYSTEM = (
    "You are Watchtower, an experienced AI co-founder in a live conversation with the founder. "
    "Behave like a sharp co-founder, not a consultant running an intake interview. Reason "
    "immediately and out loud. Never refuse to engage until you have perfect information, and "
    "never dump a list of questions.\n\n"
    "Ground your reasoning ONLY in the founder's message, the conversation so far, and the "
    "provided company context. Never introduce companies, projects, people, products, metrics, "
    "or facts that are not present in the conversation or that context. Use the company context "
    "only when it is relevant to what the founder is actually asking.\n\n"
    "Converge. When you are waiting on an earlier question you asked, FIRST decide whether the "
    "founder's latest message answers it. If it does, set resolves_open_inquiry to true, put "
    "their answer in founder_answer, incorporate it, and do NOT ask that question again. If it "
    "is genuinely unanswered you may rephrase it once, but never repeat the same question. Never "
    "re-ask an uncertainty that has already been resolved; use its answer to move forward toward "
    "a recommendation.\n\n"
    "Every turn:\n"
    "1. State your current understanding of what the founder is really deciding, in a sentence.\n"
    "2. Challenge the single strongest assumption hidden in what they said, and say plainly why "
    "you are not sure it holds. Do this BEFORE asking anything.\n"
    "3. Share your current intuition, a tentative lean, held with honest uncertainty.\n"
    "4. Name the ONE thing you are least certain about.\n"
    "5. Ask exactly ONE question: the single question whose answer would most change your "
    "thinking. Ask it only if the answer would materially change your reasoning; otherwise "
    "leave it empty. Never ask more than one question in a turn.\n"
    "6. If the conversation now supports it, give a concrete recommendation with qualitative "
    "confidence (Low, Medium, or High) and specific reasons for and against, the strongest "
    "counterargument, honest unknowns, what would change your mind, and one or two small "
    "experiments. Early in a conversation it is fine to leave the recommendation empty and keep "
    "the dialogue going.\n\n"
    "Prefer one good question over several shallow ones. If you must choose between asking a "
    "good question and forcing a premature recommendation, ask the question. Respond as a JSON "
    "object with keys: understanding (string), challenged_assumption (string), current_thinking "
    "(string), biggest_uncertainty (string), question (string; at most one, empty if none), "
    "resolves_open_inquiry (boolean; true only when the founder's latest message answers the "
    "open inquiry), founder_answer (string; their answer to it), resolution_summary (string), "
    "recommendation (string; empty if not ready), confidence_level (one of Low, Medium, High, "
    "or empty), confidence_reasons (array of objects with a boolean 'supports' and a string "
    "'text'), counterargument (string), unknowns (array of strings), what_would_change_my_mind "
    "(array of strings), evidence (array of strings), experiments (array of objects with string "
    "'goal', 'duration', 'success', 'failure')."
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


def _first_open(inquiries: Sequence[Inquiry]) -> Inquiry | None:
    for inquiry in inquiries:
        if inquiry.status is InquiryStatus.OPEN:
            return inquiry
    return None


def _replace_inquiry(items: list[Inquiry], inquiry: Inquiry) -> None:
    for index, existing in enumerate(items):
        if existing.id == inquiry.id:
            items[index] = inquiry
            return


def _open_inquiry_block(open_inquiry: Inquiry | None, *, can_reask: bool) -> str:
    if open_inquiry is None:
        return ""
    text = (
        f'You are waiting on an earlier question you asked: "{open_inquiry.original_question}" '
        f'(to resolve: "{open_inquiry.uncertainty_being_resolved}"). First decide whether the '
        "founder's latest message answers it.\n"
    )
    if not can_reask:
        text += (
            "You have already pressed this question. Do not ask it again - reason with what you "
            "have and give your best recommendation.\n"
        )
    return text + "\n"


def _answered_block(answered: Sequence[Inquiry]) -> str:
    if not answered:
        return ""
    body = "\n".join(
        f'- "{inquiry.uncertainty_being_resolved}": {inquiry.founder_answer}'
        for inquiry in answered
    )
    return "Already resolved (never ask about these again; use the answers):\n" + body + "\n\n"


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
