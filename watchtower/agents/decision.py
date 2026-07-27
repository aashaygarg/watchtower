"""Decision service: port and a placeholder implementation.

The decision service turns the founder's context and the day's research briefing
into concrete, prioritized recommendations. The real implementation will be a
set of **LangGraph** reasoning nodes; the placeholder here derives deterministic
recommendations with simple heuristics and no LLM calls.

Callers depend on the :class:`DecisionService` protocol, never on a concrete
class, so the placeholder can be swapped for the real service without changes
upstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from watchtower.startup.enums import GoalStatus
from watchtower.startup.models import GoalId, HypothesisId
from watchtower.startup.workspace import StartupWorkspace
from watchtower.tools.research import ResearchBriefing


class Priority(StrEnum):
    """Relative urgency of a recommendation."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class DecisionRecommendation:
    """A single recommended next action.

    Attributes:
        title: A short statement of what is recommended.
        rationale: Why the recommendation is being made.
        priority: Relative urgency. Defaults to :attr:`Priority.MEDIUM`.
        suggested_action: A concrete next step the founder can take.
        related_goal_id: The goal this recommendation serves, if any.
        related_hypothesis_id: The hypothesis this recommendation targets, if any.
    """

    title: str
    rationale: str
    priority: Priority = Priority.MEDIUM
    suggested_action: str = ""
    related_goal_id: GoalId | None = None
    related_hypothesis_id: HypothesisId | None = None


class DecisionService(Protocol):
    """Port for turning context and research into recommendations."""

    def recommend(
        self,
        workspace: StartupWorkspace,
        research: ResearchBriefing,
    ) -> tuple[DecisionRecommendation, ...]:
        """Return prioritized recommendations for the given inputs."""
        ...


class PlaceholderDecisionService:
    """Deterministic, LLM-free stand-in for the real decision service.

    Applies a few transparent heuristics so the morning dashboard shows
    plausible recommendations without any reasoning model.
    """

    def recommend(
        self,
        workspace: StartupWorkspace,
        research: ResearchBriefing,
    ) -> tuple[DecisionRecommendation, ...]:
        recommendations: list[DecisionRecommendation] = []

        # 1. De-risk the least-validated assumption.
        if workspace.hypotheses:
            weakest = min(workspace.hypotheses, key=lambda hypothesis: hypothesis.confidence)
            recommendations.append(
                DecisionRecommendation(
                    title=f"De-risk: {weakest.statement}",
                    rationale=(
                        f"This is the least-validated assumption at "
                        f"{weakest.confidence:.0%} confidence."
                    ),
                    priority=Priority.HIGH,
                    suggested_action="Design a cheap experiment to test it this week.",
                    related_hypothesis_id=weakest.id,
                )
            )

        # 2. Protect focus on the first active goal.
        active_goals = [goal for goal in workspace.goals if goal.status == GoalStatus.ACTIVE]
        if active_goals:
            goal = active_goals[0]
            recommendations.append(
                DecisionRecommendation(
                    title=f"Protect focus on: {goal.title}",
                    rationale="One active goal should own the team's attention today.",
                    priority=Priority.MEDIUM,
                    suggested_action="Timebox the day around this goal's next milestone.",
                    related_goal_id=goal.id,
                )
            )

        # 3. Nudge toward real research while the briefing is mock data.
        if research.is_placeholder:
            recommendations.append(
                DecisionRecommendation(
                    title="Wire in live research",
                    rationale="Today's briefing uses placeholder data.",
                    priority=Priority.LOW,
                    suggested_action="Replace PlaceholderResearchService with GPT-Researcher.",
                )
            )

        return tuple(recommendations)
