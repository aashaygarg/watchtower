"""Research service: port, placeholder, and GPT-Researcher implementation.

The research service gathers external context relevant to the startup's open
questions. :class:`GPTResearchService` wraps **GPT-Researcher** to produce
structured findings from the workspace context; :class:`PlaceholderResearchService`
returns deterministic, LLM-free mock data and doubles as the graceful-degradation
fallback when GPT-Researcher is unavailable.

Callers depend on the :class:`ResearchService` protocol, never on a concrete
class, so implementations can be swapped without changes upstream.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from watchtower.startup.enums import EvidenceSource
from watchtower.startup.models import Evidence, EvidenceId, HypothesisId
from watchtower.startup.workspace import StartupWorkspace


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
    """The full set of findings produced for one morning routine.

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


class ResearchService(Protocol):
    """Port for producing a research briefing from a workspace."""

    def investigate(self, workspace: StartupWorkspace) -> ResearchBriefing:
        """Return a research briefing for the given ``workspace``."""
        ...


class PlaceholderResearchService:
    """Deterministic, LLM-free stand-in for the real research service.

    Produces one mock finding per hypothesis so downstream stages and the
    dashboard have realistic-looking data to work with.
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


class ResearchUnavailableError(RuntimeError):
    """Raised when a research run cannot be performed (e.g. GPT-Researcher missing)."""


class ResearchRunner(Protocol):
    """Port for executing a research query and returning raw results."""

    def run(self, query: str) -> RawResearch:
        """Run research for ``query`` or raise :class:`ResearchUnavailableError`."""
        ...


def build_research_query(workspace: StartupWorkspace) -> str:
    """Compose a research query from the workspace context.

    Draws on the mission (from ``vision.md``), goals, strategies, and hypotheses
    so the research is grounded in the startup's current understanding.
    """
    startup = workspace.startup
    parts = [f"Startup: {startup.name}."]
    if startup.mission:
        parts.append(f"Mission: {startup.mission}")
    if workspace.goals:
        parts.append("Goals: " + "; ".join(goal.title for goal in workspace.goals))
    if workspace.strategies:
        parts.append("Strategies: " + "; ".join(item.title for item in workspace.strategies))
    if workspace.hypotheses:
        parts.append(
            "Hypotheses to pressure-test: "
            + "; ".join(item.statement for item in workspace.hypotheses)
        )
    parts.append(
        "Find new evidence, relevant competitor updates, important scientific "
        "papers, and market changes bearing on these hypotheses."
    )
    return "\n".join(parts)


class GPTResearchService:
    """Research service backed by GPT-Researcher.

    Builds a research query from the workspace context, runs GPT-Researcher via
    an injectable :class:`ResearchRunner`, and maps the result into a structured
    :class:`ResearchBriefing`. If the runner is unavailable or fails for any
    reason, it degrades gracefully to ``fallback`` (the placeholder service by
    default), so ``watchtower morning`` always produces a briefing.
    """

    def __init__(
        self,
        *,
        runner: ResearchRunner | None = None,
        fallback: ResearchService | None = None,
    ) -> None:
        self._runner = runner or GPTResearcherRunner()
        self._fallback = fallback or PlaceholderResearchService()

    def investigate(self, workspace: StartupWorkspace) -> ResearchBriefing:
        query = build_research_query(workspace)
        try:
            raw = self._runner.run(query)
        except Exception:
            # Degrade gracefully to the fallback on any research failure.
            return self._fallback.investigate(workspace)
        return _briefing_from_raw(raw)


class GPTResearcherRunner:
    """Runs GPT-Researcher to gather and classify research sources.

    GPT-Researcher and its API keys are optional. If the package is not installed
    or a run fails, :meth:`run` raises :class:`ResearchUnavailableError` so the
    service can degrade gracefully.
    """

    def __init__(self, *, report_type: str = "research_report") -> None:
        self._report_type = report_type

    def run(self, query: str) -> RawResearch:
        researcher_cls = _import_gpt_researcher()
        try:
            report, raw_sources = asyncio.run(self._conduct(researcher_cls, query))
        except ResearchUnavailableError:
            raise
        except Exception as exc:
            # Surface any GPT-Researcher run failure as an unavailable error.
            raise ResearchUnavailableError(f"GPT-Researcher run failed: {exc}") from exc
        sources = tuple(_classify_source(item) for item in raw_sources)
        return RawResearch(
            summary=_first_paragraph(str(report)),
            sources=sources,
            confidence=_confidence_from_sources(sources),
        )

    async def _conduct(self, researcher_cls: Any, query: str) -> tuple[str, list[Any]]:
        researcher = researcher_cls(query=query, report_type=self._report_type)
        await researcher.conduct_research()
        report = await researcher.write_report()
        return str(report), await _collect_sources(researcher)


def _import_gpt_researcher() -> Any:
    try:
        from gpt_researcher import GPTResearcher
    except ImportError as exc:
        raise ResearchUnavailableError(
            "gpt-researcher is not installed; install the 'research' extra to enable live research"
        ) from exc
    return GPTResearcher


async def _collect_sources(researcher: Any) -> list[Any]:
    for method_name in ("get_research_sources", "get_source_urls"):
        getter = getattr(researcher, method_name, None)
        if not callable(getter):
            continue
        result = getter()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return list(result)
    return []


def _classify_source(raw_source: Any) -> ResearchSource:
    if isinstance(raw_source, str):
        return ResearchSource(title=raw_source, url=raw_source, kind=_kind_for_url(raw_source))
    url = raw_source.get("url")
    title = str(raw_source.get("title") or url or "source")
    snippet = str(raw_source.get("content") or raw_source.get("raw_content") or "")[:280]
    return ResearchSource(title=title, url=url, snippet=snippet, kind=_kind_for_url(str(url or "")))


def _kind_for_url(url: str) -> SourceKind:
    lowered = url.lower()
    paper_hosts = (
        "arxiv.org",
        "doi.org",
        "pubmed",
        "ncbi.nlm.nih",
        "nature.com",
        "biorxiv",
        "medrxiv",
    )
    competitor_hosts = ("crunchbase", "techcrunch", "g2.com", "producthunt", "/pricing")
    if any(host in lowered for host in paper_hosts):
        return SourceKind.PAPER
    if any(host in lowered for host in competitor_hosts):
        return SourceKind.COMPETITOR
    if lowered:
        return SourceKind.MARKET
    return SourceKind.OTHER


def _confidence_from_sources(sources: tuple[ResearchSource, ...]) -> float:
    return round(min(1.0, 0.3 + 0.1 * len(sources)), 2)


def _first_paragraph(report: str) -> str:
    paragraph: list[str] = []
    for raw in report.splitlines():
        line = raw.strip()
        if line.startswith("#") or not line:
            if paragraph:
                break
            continue
        paragraph.append(line)
    return " ".join(paragraph)


def _evidence_source_for_kind(kind: SourceKind) -> EvidenceSource:
    mapping = {
        SourceKind.COMPETITOR: EvidenceSource.MARKET_RESEARCH,
        SourceKind.PAPER: EvidenceSource.EXPERT_OPINION,
        SourceKind.MARKET: EvidenceSource.MARKET_RESEARCH,
    }
    return mapping.get(kind, EvidenceSource.OTHER)


def _findings_from_raw(raw: RawResearch) -> tuple[ResearchFinding, ...]:
    if not raw.summary and not raw.sources:
        return ()
    return (
        ResearchFinding(
            topic="Research summary",
            summary=raw.summary or "GPT-Researcher completed with no summary text.",
            key_points=tuple(source.title for source in raw.sources[:5]),
            sources=tuple(source.url for source in raw.sources if source.url),
        ),
    )


def _briefing_from_raw(raw: RawResearch) -> ResearchBriefing:
    competitor_updates = tuple(
        CompetitorUpdate(name=source.title, summary=source.snippet, url=source.url)
        for source in raw.sources
        if source.kind is SourceKind.COMPETITOR
    )
    scientific_papers = tuple(
        ScientificPaper(title=source.title, summary=source.snippet, url=source.url)
        for source in raw.sources
        if source.kind is SourceKind.PAPER
    )
    market_changes = tuple(
        MarketChange(summary=source.snippet or source.title, url=source.url)
        for source in raw.sources
        if source.kind is SourceKind.MARKET
    )
    new_evidence = tuple(
        Evidence(
            id=EvidenceId(f"ev-{index}"),
            summary=source.title,
            source=_evidence_source_for_kind(source.kind),
            source_reference=source.url,
            detail=source.snippet,
        )
        for index, source in enumerate(raw.sources, start=1)
    )
    return ResearchBriefing(
        findings=_findings_from_raw(raw),
        generated_at=datetime.now(),
        is_placeholder=False,
        new_evidence=new_evidence,
        competitor_updates=competitor_updates,
        scientific_papers=scientific_papers,
        market_changes=market_changes,
        confidence=raw.confidence,
    )
