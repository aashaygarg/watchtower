"""Watchtower's core thinking capability.

:func:`think` takes a startup problem and reasons to a recommendation the way a
sharp co-founder would. It frames the problem, forms competing hypotheses, red-
teams them with internal adversarial reasoning first, and reaches for external
research only when the *evidence is insufficient* to judge the hypotheses. It
does the minimum thinking necessary to reach a well-supported recommendation.

This is one concrete capability, not a framework. Abstractions will be extracted
only after several real problems have been worked end to end. The control flow
is deliberately simple today, but nothing here assumes thinking is linear: the
red team can send us back out for evidence before we conclude.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from watchtower.llm import LLM, system, user
from watchtower.startup.workspace import StartupWorkspace
from watchtower.tools.research import ResearchBriefing, ResearchService


@dataclass(frozen=True, slots=True)
class ThinkingResult:
    """The outcome of one pass of thinking about a problem.

    Attributes:
        problem: The problem as the founder posed it.
        recommendation: Watchtower's recommended answer.
        confidence: How well the evidence supports the recommendation (0.0-1.0).
            This is an *outcome* of reasoning, never a trigger for it.
        hypotheses: The competing hypotheses that were considered.
        evidence: The evidence weighed, internal and (if gathered) external.
        red_team: The strongest arguments against the recommendation.
        unknowns: What remains genuinely uncertain.
        what_would_change_my_mind: Observations that would overturn the answer.
        used_external_research: Whether external research was needed.
    """

    problem: str
    recommendation: str
    confidence: float
    hypotheses: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    red_team: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    what_would_change_my_mind: tuple[str, ...] = ()
    used_external_research: bool = False


def think(
    problem: str,
    *,
    workspace: StartupWorkspace,
    llm: LLM,
    research: ResearchService,
    history: Sequence[str] = (),
) -> ThinkingResult:
    """Think through ``problem`` and return a recommendation.

    Args:
        problem: The startup problem to reason about.
        workspace: The company context to reason within.
        llm: The language model used for reasoning.
        research: The research capability, used only when evidence is lacking.
        history: Prior conversation turns, for follow-up/debate.

    Returns:
        A :class:`ThinkingResult`.
    """
    context = _context_summary(workspace)
    framing = _frame_and_hypothesize(llm, problem, context, history)

    # Red-team internally first, with no external evidence.
    assessment = _red_team(llm, problem, context, framing.hypotheses, evidence=())
    evidence = list(assessment.internal_evidence)
    used_external = False

    # Evidence-sufficiency gate: escalate to external research only when the
    # internal evidence is not enough to judge the hypotheses.
    if not assessment.evidence_sufficient and assessment.open_questions:
        external = _evidence_from_briefing(research.investigate(workspace))
        if external:
            evidence.extend(external)
            assessment = _red_team(
                llm, problem, context, framing.hypotheses, evidence=tuple(external)
            )
            used_external = True

    recommendation = _recommend(
        llm, problem, context, framing.hypotheses, assessment, tuple(evidence)
    )

    return ThinkingResult(
        problem=problem,
        recommendation=recommendation.claim,
        confidence=recommendation.confidence,
        hypotheses=framing.hypotheses,
        evidence=tuple(evidence),
        red_team=assessment.red_team,
        unknowns=recommendation.unknowns or assessment.open_questions,
        what_would_change_my_mind=recommendation.what_would_change_my_mind,
        used_external_research=used_external,
    )


# --------------------------------------------------------------------------- #
# Internal reasoning steps
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class _Framing:
    restatement: str
    success_criteria: str
    hypotheses: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Assessment:
    red_team: tuple[str, ...]
    internal_evidence: tuple[str, ...]
    open_questions: tuple[str, ...]
    evidence_sufficient: bool


@dataclass(frozen=True, slots=True)
class _Recommendation:
    claim: str
    confidence: float
    unknowns: tuple[str, ...]
    what_would_change_my_mind: tuple[str, ...]


_FRAME_SYSTEM = (
    "You are Watchtower, an internal AI co-founder. Think like a sharp, skeptical "
    "co-founder. Given a startup problem and company context, restate the problem "
    "crisply, state what a good answer looks like, and propose 2-4 competing "
    "hypotheses. Respond as a JSON object with keys: restatement (string), "
    "success_criteria (string), hypotheses (array of strings)."
)

_REDTEAM_SYSTEM = (
    "You are Watchtower running an internal red team. Argue against each hypothesis "
    "using reasoning and the provided context and evidence; list the strongest "
    "disconfirming points. Then judge whether the available evidence is sufficient to "
    "choose between the hypotheses, or whether specific external research is required. "
    "Respond as a JSON object with keys: red_team (array of strings), internal_evidence "
    "(array of strings), open_questions (array of strings), evidence_sufficient (boolean)."
)

_RECOMMEND_SYSTEM = (
    "You are Watchtower producing a final recommendation for the founder. Choose the "
    "best-supported hypothesis given the red-team critique and the evidence. State a "
    "clear recommendation, a confidence between 0 and 1 reflecting how well the evidence "
    "supports it, the key unknowns, and what would change your mind. Respond as a JSON "
    "object with keys: recommendation (string), confidence (number), unknowns (array of "
    "strings), what_would_change_my_mind (array of strings)."
)


def _frame_and_hypothesize(
    llm: LLM, problem: str, context: str, history: Sequence[str]
) -> _Framing:
    data = llm.complete_json(
        [
            system(_FRAME_SYSTEM),
            user(f"Company context:\n{context}\n\n{_history_block(history)}Problem:\n{problem}"),
        ]
    )
    return _Framing(
        restatement=str(data.get("restatement", problem)),
        success_criteria=str(data.get("success_criteria", "")),
        hypotheses=_str_tuple(data.get("hypotheses")),
    )


def _red_team(
    llm: LLM,
    problem: str,
    context: str,
    hypotheses: tuple[str, ...],
    *,
    evidence: tuple[str, ...],
) -> _Assessment:
    prompt = (
        f"Problem:\n{problem}\n\n"
        f"Context:\n{context}\n\n"
        f"Hypotheses:\n{_bullets(hypotheses)}\n\n"
        f"Evidence:\n{_bullets(evidence) or '(none yet)'}"
    )
    data = llm.complete_json([system(_REDTEAM_SYSTEM), user(prompt)])
    return _Assessment(
        red_team=_str_tuple(data.get("red_team")),
        internal_evidence=_str_tuple(data.get("internal_evidence")),
        open_questions=_str_tuple(data.get("open_questions")),
        evidence_sufficient=bool(data.get("evidence_sufficient", True)),
    )


def _recommend(
    llm: LLM,
    problem: str,
    context: str,
    hypotheses: tuple[str, ...],
    assessment: _Assessment,
    evidence: tuple[str, ...],
) -> _Recommendation:
    prompt = (
        f"Problem:\n{problem}\n\n"
        f"Context:\n{context}\n\n"
        f"Hypotheses:\n{_bullets(hypotheses)}\n\n"
        f"Red-team critique:\n{_bullets(assessment.red_team) or '(none)'}\n\n"
        f"Evidence:\n{_bullets(evidence) or '(none)'}"
    )
    data = llm.complete_json([system(_RECOMMEND_SYSTEM), user(prompt)])
    return _Recommendation(
        claim=str(data.get("recommendation", "")),
        confidence=_clamp_float(data.get("confidence")),
        unknowns=_str_tuple(data.get("unknowns")),
        what_would_change_my_mind=_str_tuple(data.get("what_would_change_my_mind")),
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


def _evidence_from_briefing(briefing: ResearchBriefing) -> list[str]:
    items = [finding.summary for finding in briefing.findings]
    items.extend(evidence.summary for evidence in briefing.new_evidence)
    return [item for item in items if item]


def _history_block(history: Sequence[str]) -> str:
    if not history:
        return ""
    return "Conversation so far:\n" + "\n".join(history) + "\n\n"


def _bullets(items: Sequence[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _str_tuple(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def _clamp_float(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
