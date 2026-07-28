"""Rich rendering of a dialogue turn as a co-founder's reply.

The founder only ever has a conversation. This renders one turn: the reasoning
(understanding, a challenged assumption, a current lean, the biggest uncertainty)
as flowing speech, at most one question, and — only when the conversation
supports it — a recommendation with its supporting detail.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich import box
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from watchtower.domain.judgment import Experiment, ThinkingResult


def render_thinking(result: ThinkingResult, console: Console) -> None:
    """Render one dialogue turn to ``console``."""
    sections: list[RenderableType] = []

    reasoning = _reasoning_block(result)
    if reasoning is not None:
        sections.append(reasoning)
    if result.question:
        sections.append(_question_block(result.question))

    if result.recommendation:
        sections.append(_recommendation_block(result))
        if result.confidence_level:
            sections.append(_confidence_block(result))
        if result.evidence:
            sections.append(_list_block("Supporting evidence", result.evidence, "green"))
        if result.counterargument:
            sections.append(
                _labeled_block("Strongest counterargument", result.counterargument, "red")
            )
        if result.unknowns:
            sections.append(_list_block("Unknowns", result.unknowns, "yellow"))
        if result.what_would_change_my_mind:
            sections.append(
                _list_block("What would change my mind", result.what_would_change_my_mind, "cyan")
            )
        if result.experiments:
            sections.append(_experiments_block(result.experiments))

    if not sections:
        sections.append(Text("(no response)", style="dim"))

    console.print(
        Panel(
            Group(*sections),
            title="[bold]Watchtower[/bold]",
            border_style="blue",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def _reasoning_block(result: ThinkingResult) -> RenderableType | None:
    paragraphs = [
        part
        for part in (result.understanding, result.challenged_assumption, result.current_thinking)
        if part
    ]
    if result.biggest_uncertainty:
        paragraphs.append(f"What I'm least sure about: {result.biggest_uncertainty}")
    if not paragraphs:
        return None
    return Text("\n\n".join(paragraphs))


def _question_block(question: str) -> RenderableType:
    return Text(question, style="bold cyan")


def _labeled_block(title: str, text: str, style: str) -> RenderableType:
    body = Text()
    body.append(f"{title}\n", style=f"bold {style}")
    body.append(text)
    return body


def _list_block(title: str, items: Sequence[str], style: str) -> RenderableType:
    body = Text()
    body.append(f"{title}\n", style=f"bold {style}")
    for item in items:
        body.append(f"  - {item}\n")
    return body


def _recommendation_block(result: ThinkingResult) -> RenderableType:
    body = Text()
    body.append("Recommendation\n", style="bold blue")
    body.append(result.recommendation or "(no recommendation)")
    return body


def _confidence_block(result: ThinkingResult) -> RenderableType:
    body = Text()
    body.append(f"Confidence: {result.confidence_level}\n", style="bold")
    for reason in result.confidence_reasons:
        mark = "\u2713" if reason.supports else "\u2717"
        style = "green" if reason.supports else "red"
        body.append(f"  {mark} ", style=style)
        body.append(f"{reason.text}\n")
    return body


def _experiments_block(experiments: Sequence[Experiment]) -> RenderableType:
    body = Text()
    body.append("Experiments\n", style="bold blue")
    for experiment in experiments:
        body.append(f"  {experiment.goal}\n", style="bold")
        for label, value in (
            ("Duration", experiment.duration),
            ("Success", experiment.success),
            ("Failure", experiment.failure),
        ):
            if value:
                body.append(f"    {label}: {value}\n", style="dim")
    return body
