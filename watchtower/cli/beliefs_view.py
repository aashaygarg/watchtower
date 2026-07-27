"""Rich rendering for the belief engine.

Shows what Watchtower currently believes, and a compact summary of how a
conversation changed its worldview.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from watchtower.beliefs.store import BeliefStore
from watchtower.domain.beliefs import (
    Belief,
    BeliefAction,
    BeliefStatus,
    BeliefUpdate,
)

_LIVE = (BeliefStatus.ACTIVE, BeliefStatus.WEAKENING)
_CONFIDENCE_STYLE = {"high": "green", "medium": "yellow", "low": "red"}


def render_beliefs(store: BeliefStore, console: Console) -> None:
    """Render what Watchtower currently believes about the company."""
    beliefs = [belief for belief in store.all() if belief.status in _LIVE]
    if not beliefs:
        console.print(
            "[dim]No beliefs yet. Have a conversation and Watchtower will form some.[/dim]"
        )
        return

    beliefs.sort(key=lambda belief: (belief.status is BeliefStatus.WEAKENING, belief.title))
    body = Text()
    for index, belief in enumerate(beliefs):
        if index:
            body.append("\n\n")
        _append_belief(body, belief)

    console.print(
        Panel(
            body,
            title="[bold]What Watchtower believes[/bold]",
            border_style="blue",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    _append_recently_changed(store, console)


def render_belief_updates(updates: Sequence[BeliefUpdate], console: Console) -> None:
    """Render a compact summary of how a conversation changed the worldview."""
    changes = [update for update in updates if update.action is not BeliefAction.NO_CHANGE]
    if not changes:
        console.print("\n[dim]This conversation did not change Watchtower's beliefs.[/dim]")
        return
    console.print("\n[bold]Worldview updated:[/bold]")
    for update in changes:
        label = update.title or update.belief_id or "belief"
        console.print(f"  [cyan]{update.action.value}[/cyan] {label}: {update.rationale}")


def _append_belief(body: Text, belief: Belief) -> None:
    style = _CONFIDENCE_STYLE.get(belief.confidence.value, "white")
    body.append(belief.title, style="bold")
    body.append(f"  [{belief.confidence.value}]", style=style)
    if belief.status is BeliefStatus.WEAKENING:
        body.append("  (weakening)", style="dim")
    if belief.description:
        body.append(f"\n{belief.description}", style="dim")
    for evidence in belief.supporting_evidence:
        body.append("\n  \u2713 ", style="green")
        body.append(evidence)
    for evidence in belief.contradicting_evidence:
        body.append("\n  \u2717 ", style="red")
        body.append(evidence)


def _append_recently_changed(store: BeliefStore, console: Console) -> None:
    changed = [update for update in store.history() if update.action is not BeliefAction.NO_CHANGE]
    recent = changed[-5:]
    if not recent:
        return
    console.print("[bold]Recently changed[/bold]")
    for update in reversed(recent):
        label = update.title or update.belief_id or "belief"
        console.print(f"  [cyan]{update.action.value}[/cyan] {label}: {update.rationale}")
