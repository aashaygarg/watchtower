"""Rich rendering of a thinking result as a co-founder's reply.

The founder only ever has a conversation; this turns Watchtower's reasoning into
a single, readable reply with first-class sections.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich import box
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.text import Text

from watchtower.cognition import ThinkingResult


def render_thinking(result: ThinkingResult, console: Console) -> None:
    """Render ``result`` to ``console`` as a co-founder's reply."""
    sections: list[RenderableType] = [_recommendation(result)]

    sections.extend(
        _section(title, items, style)
        for title, items, style in (
            ("Supporting evidence", result.evidence, "green"),
            ("Red Team", result.red_team, "red"),
            ("Unknowns", result.unknowns, "yellow"),
            ("What would change my mind", result.what_would_change_my_mind, "cyan"),
        )
        if items
    )

    if not result.used_external_research:
        sections.append(Text("Reasoned from internal evidence only.", style="dim"))

    console.print(
        Panel(
            Group(*sections),
            title="[bold]Watchtower[/bold]",
            border_style="blue",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def _recommendation(result: ThinkingResult) -> RenderableType:
    body = Text()
    body.append("Recommendation\n", style="bold blue")
    body.append(result.recommendation or "(no recommendation)", style="bold")
    body.append(f"\nConfidence: {result.confidence:.0%}", style="dim")
    return body


def _section(title: str, items: Sequence[str], style: str) -> RenderableType:
    body = Text()
    body.append(f"{title}\n", style=f"bold {style}")
    for item in items:
        body.append(f"  - {item}\n")
    return body
