"""Deterministic, LLM-free research provider used as a stand-in and fallback."""

from __future__ import annotations

from datetime import datetime

from watchtower.adapters.research.models import ResearchBriefing, ResearchFinding
from watchtower.startup.models import StartupWorkspace


class PlaceholderResearchService:
    """Deterministic, LLM-free stand-in for the real research service.

    Produces one mock finding per hypothesis so downstream stages have
    realistic-looking data to work with.
    """

    def investigate(self, workspace: StartupWorkspace) -> ResearchBriefing:
        findings = tuple(
            ResearchFinding(
                topic=hypothesis.statement,
                summary=(
                    "Placeholder desk research into this assumption. Signals are "
                    "mixed but broadly consistent with the current stance."
                ),
                key_points=(
                    f"Prior confidence stands at {hypothesis.confidence:.0%}.",
                    "Two comparable companies report similar demand patterns.",
                    "No blocking counter-evidence surfaced in this placeholder pass.",
                ),
                sources=(
                    "Industry landscape report (placeholder)",
                    "Competitor teardown (placeholder)",
                ),
                related_hypothesis_id=hypothesis.id,
            )
            for hypothesis in workspace.hypotheses
        )
        return ResearchBriefing(
            findings=findings,
            generated_at=datetime.now(),
            is_placeholder=True,
        )
