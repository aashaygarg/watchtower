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
from dataclasses import dataclass
from typing import Any

from watchtower.llm import LLM, system, user
from watchtower.startup.workspace import StartupWorkspace

_CONFIDENCE_LEVELS = ("Low", "Medium", "High")


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


def think(
    problem: str,
    *,
    workspace: StartupWorkspace,
    llm: LLM,
    history: Sequence[str] = (),
    beliefs: Sequence[str] = (),
) -> ThinkingResult:
    """Take one turn of dialogue about ``problem``.

    Reasoning is grounded only in ``problem``, the conversation ``history``, the
    explicitly loaded ``workspace`` context, and ``beliefs`` (Watchtower's prior
    understanding, which it may disagree with) - nothing else.
    """
    context = _context_summary(workspace)
    prompt = (
        "Company context (background - use only if it is relevant to the question):\n"
        f"{context}\n\n"
        f"{_beliefs_block(beliefs)}"
        f"{_history_block(history)}"
        f"Founder:\n{problem}"
    )
    data = llm.complete_json([system(_DIALOGUE_SYSTEM), user(prompt)])

    recommendation = str(data.get("recommendation", "")).strip()
    return ThinkingResult(
        problem=problem,
        understanding=str(data.get("understanding", "")).strip(),
        challenged_assumption=str(data.get("challenged_assumption", "")).strip(),
        current_thinking=str(data.get("current_thinking", "")).strip(),
        biggest_uncertainty=str(data.get("biggest_uncertainty", "")).strip(),
        question=str(data.get("question", "")).strip(),
        recommendation=recommendation,
        confidence_level=_confidence_level(data.get("confidence_level")) if recommendation else "",
        confidence_reasons=_parse_reasons(data.get("confidence_reasons")) if recommendation else (),
        counterargument=str(data.get("counterargument", "")).strip(),
        unknowns=_str_tuple(data.get("unknowns")),
        what_would_change_my_mind=_str_tuple(data.get("what_would_change_my_mind")),
        evidence=_str_tuple(data.get("evidence")),
        experiments=_parse_experiments(data.get("experiments")) if recommendation else (),
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
