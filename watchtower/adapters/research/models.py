"""Research result types produced by a research provider.

These are the structured outputs a :class:`~watchtower.ports.research.ResearchProvider`
returns. They live with the research adapters because they are coupled to the
startup workspace domain (findings link to hypotheses; evidence uses the workspace
evidence types).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from watchtower.startup.models import Evidence, HypothesisId


@dataclass(frozen=True, slots=True)
class ResearchFinding:
    """A single unit of research output.

    Attributes:
        topic: The question or theme the finding addresses.
        summary: A short synthesis of what was learned.
        key_points: Notable bullet points supporting the summary.
        sources: Human-readable references the finding draws on.
        related_hypothesis_id: The hypothesis this finding informs, if any.
    """

    topic: str
    summary: str
    key_points: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    related_hypothesis_id: HypothesisId | None = None


@dataclass(frozen=True, slots=True)
class CompetitorUpdate:
    """A relevant update about a competitor.

    Attributes:
        name: The competitor's name (or the source title).
        summary: What changed and why it matters.
        url: A link to the source, if available.
    """

    name: str
    summary: str = ""
    url: str | None = None


@dataclass(frozen=True, slots=True)
class ScientificPaper:
    """An important scientific paper surfaced by research.

    Attributes:
        title: The paper title.
        summary: A short synthesis of the paper's relevance.
        url: A link to the paper, if available.
    """

    title: str
    summary: str = ""
    url: str | None = None


@dataclass(frozen=True, slots=True)
class MarketChange:
    """A notable change in the market.

    Attributes:
        summary: What changed and why it matters.
        url: A link to the source, if available.
    """

    summary: str
    url: str | None = None


@dataclass(frozen=True, slots=True)
class ResearchBriefing:
    """The full set of findings produced for one research run.

    Attributes:
        findings: The individual research findings.
        generated_at: When the briefing was produced, if recorded.
        is_placeholder: ``True`` when the briefing is mock data rather than the
            output of a real research run.
        new_evidence: New evidence surfaced by the research.
        competitor_updates: Relevant competitor updates.
        scientific_papers: Important scientific papers.
        market_changes: Notable market changes.
        confidence: Overall confidence score for the briefing, from 0.0 to 1.0.
    """

    findings: tuple[ResearchFinding, ...] = ()
    generated_at: datetime | None = None
    is_placeholder: bool = True
    new_evidence: tuple[Evidence, ...] = ()
    competitor_updates: tuple[CompetitorUpdate, ...] = ()
    scientific_papers: tuple[ScientificPaper, ...] = ()
    market_changes: tuple[MarketChange, ...] = ()
    confidence: float = 0.0


class SourceKind(StrEnum):
    """Classification of a research source."""

    COMPETITOR = "competitor"
    PAPER = "paper"
    MARKET = "market"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ResearchSource:
    """A single classified source returned by a research run.

    Attributes:
        title: The source title.
        url: The source URL, if any.
        snippet: A short excerpt of the source content.
        kind: How the source has been classified.
    """

    title: str
    url: str | None = None
    snippet: str = ""
    kind: SourceKind = SourceKind.OTHER


@dataclass(frozen=True, slots=True)
class RawResearch:
    """The raw result of a research run, before mapping to a briefing.

    Attributes:
        summary: A short synthesis of the research.
        sources: The classified sources gathered.
        confidence: An overall confidence score from 0.0 to 1.0.
    """

    summary: str = ""
    sources: tuple[ResearchSource, ...] = ()
    confidence: float = 0.5
