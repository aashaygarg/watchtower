"""Rich rendering of the morning dashboard.

This is the presentation layer for :class:`~watchtower.graphs.morning.MorningReport`.
It contains no domain logic; it only turns a report into terminal output.
"""

from __future__ import annotations

from rich import box
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from watchtower.agents.decision import DecisionRecommendation, Priority
from watchtower.graphs.morning import MorningReport
from watchtower.startup.enums import GoalStatus, HypothesisStatus
from watchtower.startup.models import Goal, Hypothesis
from watchtower.tools.research import ResearchBriefing

_GOAL_STATUS_STYLES: dict[GoalStatus, str] = {
    GoalStatus.PROPOSED: "cyan",
    GoalStatus.ACTIVE: "green",
    GoalStatus.ACHIEVED: "bright_green",
    GoalStatus.BLOCKED: "red",
    GoalStatus.ABANDONED: "dim",
}

_HYPOTHESIS_STATUS_STYLES: dict[HypothesisStatus, str] = {
    HypothesisStatus.UNTESTED: "cyan",
    HypothesisStatus.TESTING: "yellow",
    HypothesisStatus.SUPPORTED: "green",
    HypothesisStatus.REFUTED: "red",
    HypothesisStatus.INCONCLUSIVE: "magenta",
}

_PRIORITY_STYLES: dict[Priority, str] = {
    Priority.HIGH: "bold red",
    Priority.MEDIUM: "yellow",
    Priority.LOW: "dim",
}


def render_morning(report: MorningReport, console: Console | None = None) -> None:
    """Render ``report`` to the terminal.

    Args:
        report: The assembled morning report.
        console: The Rich console to print to. A new one is created if omitted.
    """
    console = console or Console()
    startup = report.workspace.startup

    sections: list[RenderableType] = [
        _header(report),
        _goals_table(report.workspace.goals),
        _hypotheses_table(report.workspace.hypotheses),
        _research_panel(report.research),
        _recommendations_table(report.recommendations),
    ]

    console.print()
    console.print(
        Panel(
            Group(*sections),
            title=f"[bold]{startup.name}[/bold] Morning Briefing",
            border_style="blue",
            box=box.HEAVY,
            padding=(1, 2),
        )
    )


def _header(report: MorningReport) -> RenderableType:
    startup = report.workspace.startup
    when = report.generated_at.strftime("%A, %d %B %Y at %H:%M")
    body = Text()
    body.append(startup.mission or "(no mission set)", style="italic")
    body.append(f"\n{when}", style="dim")
    return Panel(body, border_style="blue", box=box.ROUNDED)


def _goals_table(goals: tuple[Goal, ...]) -> RenderableType:
    table = Table(title="Goals", box=box.SIMPLE_HEAD, title_style="bold", expand=True)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Goal")
    table.add_column("Status", no_wrap=True)
    table.add_column("Target", no_wrap=True)

    if not goals:
        table.add_row("-", "[dim]No goals defined[/dim]", "-", "-")
        return table

    for goal in goals:
        style = _GOAL_STATUS_STYLES.get(goal.status, "white")
        target = goal.target_value or "-"
        if goal.target_metric:
            target = f"{target} {goal.target_metric}"
        table.add_row(
            goal.id,
            goal.title,
            f"[{style}]{goal.status.value}[/{style}]",
            target,
        )
    return table


def _hypotheses_table(hypotheses: tuple[Hypothesis, ...]) -> RenderableType:
    table = Table(title="Hypotheses", box=box.SIMPLE_HEAD, title_style="bold", expand=True)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Statement")
    table.add_column("Status", no_wrap=True)
    table.add_column("Confidence", no_wrap=True)

    if not hypotheses:
        table.add_row("-", "[dim]No hypotheses defined[/dim]", "-", "-")
        return table

    for hypothesis in hypotheses:
        style = _HYPOTHESIS_STATUS_STYLES.get(hypothesis.status, "white")
        table.add_row(
            hypothesis.id,
            hypothesis.statement,
            f"[{style}]{hypothesis.status.value}[/{style}]",
            _confidence_bar(hypothesis.confidence),
        )
    return table


def _research_panel(research: ResearchBriefing) -> RenderableType:
    if not research.findings:
        inner: RenderableType = Text("No research findings.", style="dim")
    else:
        finding_panels: list[RenderableType] = []
        for finding in research.findings:
            body = Text()
            body.append(finding.summary)
            for point in finding.key_points:
                body.append(f"\n  - {point}", style="dim")
            if finding.sources:
                body.append(f"\n  sources: {', '.join(finding.sources)}", style="dim italic")
            finding_panels.append(
                Panel(body, title=finding.topic, border_style="grey37", box=box.MINIMAL)
            )
        inner = Group(*finding_panels)

    title = "Research Briefing"
    if research.is_placeholder:
        title += "  [dim](placeholder data - no live research)[/dim]"
    return Panel(inner, title=title, border_style="magenta", box=box.ROUNDED, padding=(0, 1))


def _recommendations_table(
    recommendations: tuple[DecisionRecommendation, ...],
) -> RenderableType:
    table = Table(title="Recommendations", box=box.SIMPLE_HEAD, title_style="bold", expand=True)
    table.add_column("Priority", no_wrap=True)
    table.add_column("Recommendation")
    table.add_column("Suggested action")

    if not recommendations:
        table.add_row("-", "[dim]No recommendations[/dim]", "-")
        return table

    order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
    for rec in sorted(recommendations, key=lambda r: order.get(r.priority, 3)):
        style = _PRIORITY_STYLES.get(rec.priority, "white")
        body = Text(rec.title, style="bold")
        if rec.rationale:
            body.append(f"\n{rec.rationale}", style="dim")
        table.add_row(
            f"[{style}]{rec.priority.value.upper()}[/{style}]",
            body,
            rec.suggested_action or "-",
        )
    return table


def _confidence_bar(value: float, width: int = 10) -> str:
    clamped = max(0.0, min(1.0, value))
    filled = round(clamped * width)
    bar = ("#" * filled) + ("." * (width - filled))
    return f"[green]{bar}[/green] {clamped:.0%}"
