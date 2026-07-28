"""Research adapters: providers that turn a workspace into a research briefing.

:class:`GPTResearchService` wraps GPT-Researcher (optional) and degrades to
:class:`PlaceholderResearchService`. Both implement the
:class:`~watchtower.ports.research.ResearchProvider` protocol.
"""

from watchtower.adapters.research.gpt_researcher import (
    GPTResearcherRunner,
    GPTResearchService,
    ResearchRunner,
    ResearchUnavailableError,
    build_research_query,
)
from watchtower.adapters.research.models import (
    CompetitorUpdate,
    MarketChange,
    RawResearch,
    ResearchBriefing,
    ResearchFinding,
    ResearchSource,
    ScientificPaper,
    SourceKind,
)
from watchtower.adapters.research.placeholder import PlaceholderResearchService

__all__ = [
    "CompetitorUpdate",
    "GPTResearchService",
    "GPTResearcherRunner",
    "MarketChange",
    "PlaceholderResearchService",
    "RawResearch",
    "ResearchBriefing",
    "ResearchFinding",
    "ResearchRunner",
    "ResearchSource",
    "ResearchUnavailableError",
    "ScientificPaper",
    "SourceKind",
    "build_research_query",
]
