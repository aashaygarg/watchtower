"""The morning routine: Watchtower's first end-to-end slice.

The routine loads the startup workspace, gathers a research briefing, and
produces decision recommendations, bundling them into a :class:`MorningReport`
for rendering.

It is deliberately plain Python today. It defines the orchestration seam that a
**LangGraph** graph will later implement, and it depends only on injectable
service protocols (:class:`~watchtower.tools.research.ResearchService` and
:class:`~watchtower.agents.decision.DecisionService`) plus a workspace loader.
Swapping the placeholders for real implementations requires no change here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from watchtower.agents.decision import DecisionRecommendation, DecisionService
from watchtower.startup.workspace import (
    StartupWorkspace,
    WorkspaceLoader,
    load_workspace,
)
from watchtower.tools.research import ResearchBriefing, ResearchService


@dataclass(frozen=True, slots=True)
class MorningReport:
    """The assembled output of one morning routine.

    Attributes:
        workspace: The startup context that was loaded.
        research: The research briefing gathered for the day.
        recommendations: The prioritized recommendations produced.
        generated_at: When the report was assembled.
    """

    workspace: StartupWorkspace
    research: ResearchBriefing
    recommendations: tuple[DecisionRecommendation, ...]
    generated_at: datetime


class MorningRoutine:
    """Orchestrates the load -> research -> decide flow.

    Args:
        research: The research service to use.
        decision: The decision service to use.
        load: The workspace loader. Defaults to the file-backed
            :func:`~watchtower.startup.workspace.load_workspace`.
    """

    def __init__(
        self,
        *,
        research: ResearchService,
        decision: DecisionService,
        load: WorkspaceLoader = load_workspace,
    ) -> None:
        self._research = research
        self._decision = decision
        self._load = load

    def run(self, path: str | Path) -> MorningReport:
        """Run the routine against the workspace at ``path``.

        Args:
            path: The startup workspace directory.

        Returns:
            The assembled :class:`MorningReport`.
        """
        workspace = self._load(path)
        research = self._research.investigate(workspace)
        recommendations = self._decision.recommend(workspace, research)
        return MorningReport(
            workspace=workspace,
            research=research,
            recommendations=recommendations,
            generated_at=datetime.now(),
        )
