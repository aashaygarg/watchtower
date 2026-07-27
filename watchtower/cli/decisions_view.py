"""Rich rendering for the decision engine: the timeline, captures, and reviews."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from watchtower.decisions.models import Decision, DecisionReview, DecisionStatus
from watchtower.decisions.store import DecisionStore

_ACTIVE = (DecisionStatus.PROPOSED, DecisionStatus.ACCEPTED)


def render_timeline(store: DecisionStore, console: Console) -> None:
    """Render the decision timeline."""
    decisions = store.all()
    if not decisions:
        console.print(
            "[dim]No decisions yet. They are recorded when you commit to an action.[/dim]"
        )
        return

    now = datetime.now()
    active = [d for d in decisions if d.status in _ACTIVE]
    completed = [d for d in decisions if d.status is DecisionStatus.COMPLETED]
    awaiting = [d for d in decisions if _is_awaiting_review(d, now)]
    reviewed = sorted(
        (d for d in decisions if d.status is DecisionStatus.REVIEWED),
        key=lambda d: d.updated_at or now,
    )[-5:]

    body = Text()
    _append_section(body, "Active decisions", active)
    _append_section(body, "Completed decisions", completed)
    _append_section(body, "Awaiting review", awaiting)
    _append_section(body, "Recently reviewed", list(reversed(reviewed)))

    console.print(
        Panel(
            body,
            title="[bold]Decision timeline[/bold]",
            border_style="blue",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def render_captured(decisions: Sequence[Decision], console: Console) -> None:
    """Announce decisions captured from a conversation (never silent)."""
    if not decisions:
        return
    console.print("\n[bold]Decision recorded:[/bold]")
    for decision in decisions:
        console.print(f"  [green]{decision.id}[/green] {decision.title}")


def render_review(review: DecisionReview, decision: Decision, console: Console) -> None:
    """Render a structured decision review."""
    body = Text()
    body.append(f"{decision.title}\n", style="bold")
    if review.verdict:
        body.append(f"Verdict: {review.verdict}\n", style="bold cyan")
    _append_list(body, "Assumptions that held", review.assumptions_that_held, "green")
    _append_list(body, "Assumptions that broke", review.assumptions_that_broke, "red")
    _append_list(body, "How beliefs changed", review.belief_changes, "magenta")
    _append_list(body, "Observed evidence", review.observed_evidence, "yellow")
    _append_list(body, "Lessons", review.lessons, "cyan")
    if review.summary:
        body.append(f"\n{review.summary}", style="dim")

    console.print(
        Panel(
            body,
            title="[bold]Decision review[/bold]",
            border_style="blue",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def _append_section(body: Text, title: str, decisions: Sequence[Decision]) -> None:
    body.append(f"{title}\n", style="bold")
    if not decisions:
        body.append("  (none)\n\n", style="dim")
        return
    for decision in decisions:
        body.append(f"  {decision.id}", style="dim")
        body.append(f"  {decision.title}")
        body.append(f"  [{decision.status.value}]\n", style="cyan")
    body.append("\n")


def _append_list(body: Text, title: str, items: Sequence[str], style: str) -> None:
    if not items:
        return
    body.append(f"\n{title}\n", style=f"bold {style}")
    for item in items:
        body.append(f"  - {item}\n")


def _is_awaiting_review(decision: Decision, now: datetime) -> bool:
    if decision.status is DecisionStatus.REVIEWED:
        return False
    if decision.status is DecisionStatus.COMPLETED:
        return True
    return decision.review_date is not None and decision.review_date <= now
