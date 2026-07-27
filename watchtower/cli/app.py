"""Typer application defining the Watchtower CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from watchtower import __version__
from watchtower.beliefs import (
    JsonBeliefStore,
    apply_updates,
    format_for_prompt,
    select_relevant,
    update_beliefs,
)
from watchtower.cli.beliefs_view import render_belief_updates, render_beliefs
from watchtower.cli.conversation import render_thinking
from watchtower.cli.decisions_view import render_captured, render_review, render_timeline
from watchtower.cognition import think
from watchtower.config import load_config
from watchtower.decisions import (
    JsonDecisionStore,
    capture_decisions,
    mark_completed,
    record_decisions,
    record_review,
    review_decision,
)
from watchtower.llm import LLMUnavailableError, build_llm
from watchtower.startup.workspace import WorkspaceError, load_workspace

app = typer.Typer(
    name="watchtower",
    help="Watchtower — a local-first AI Founder Operating System.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _belief_store(path: Path) -> JsonBeliefStore:
    return JsonBeliefStore(path / ".watchtower" / "beliefs.json")


def _decision_store(path: Path) -> JsonDecisionStore:
    return JsonDecisionStore(path / ".watchtower" / "decisions.json")


@app.command()
def version() -> None:
    """Show the Watchtower version."""
    console.print(f"[bold]watchtower[/bold] {__version__}")


@app.command()
def chat(
    path: Annotated[
        Path,
        typer.Option("--path", "-p", help="Path to the startup workspace directory."),
    ] = Path("startup"),
) -> None:
    """Talk through a startup problem with Watchtower."""
    try:
        workspace = load_workspace(path)
    except WorkspaceError as exc:
        console.print(f"[red]Could not load startup workspace:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    try:
        llm = build_llm(load_config(search_from=path).llm)
    except LLMUnavailableError as exc:
        console.print(f"[yellow]Watchtower can't reason yet:[/yellow] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[bold]Watchtower[/bold] is ready to think about [bold]{workspace.startup.name}[/bold]. "
        "Describe a problem, or type 'exit' to leave."
    )

    store = _belief_store(path)
    beliefs = store.all()
    history: list[str] = []
    inquiries = ()
    while True:
        try:
            message = console.input("\n[bold cyan]you[/bold cyan] > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if message.lower() in {"exit", "quit", ""}:
            break
        relevant = format_for_prompt(select_relevant(beliefs, message))
        result = think(
            message,
            workspace=workspace,
            llm=llm,
            history=history,
            beliefs=relevant,
            inquiries=inquiries,
        )
        render_thinking(result, console)
        inquiries = result.inquiries
        history.append(f"You: {message}")
        spoken = result.recommendation or result.current_thinking or result.understanding or ""
        if result.question:
            spoken = f"{spoken} (asked: {result.question})".strip()
        history.append(f"Watchtower: {spoken}")

    # Every conversation becomes evidence: update the worldview, never the transcript.
    if history:
        applied = apply_updates(store, update_beliefs(history, store.all(), llm))
        render_belief_updates(applied, console)
        # Record only decisions the founder explicitly committed to (never inferred).
        captured = capture_decisions(history, store.all(), llm)
        if captured:
            record_decisions(_decision_store(path), captured)
            render_captured(captured, console)

    console.print("\n[dim]Ended.[/dim]")


@app.command()
def beliefs(
    path: Annotated[
        Path,
        typer.Option("--path", "-p", help="Path to the startup workspace directory."),
    ] = Path("startup"),
) -> None:
    """Show what Watchtower currently believes about your company."""
    render_beliefs(_belief_store(path), console)


@app.command()
def decisions(
    path: Annotated[
        Path,
        typer.Option("--path", "-p", help="Path to the startup workspace directory."),
    ] = Path("startup"),
) -> None:
    """Show the decision timeline: active, completed, awaiting review, recently reviewed."""
    render_timeline(_decision_store(path), console)


@app.command()
def complete(
    decision_id: Annotated[str, typer.Argument(help="Id of the decision to mark completed.")],
    path: Annotated[
        Path,
        typer.Option("--path", "-p", help="Path to the startup workspace directory."),
    ] = Path("startup"),
) -> None:
    """Mark a decision as carried out."""
    updated = mark_completed(_decision_store(path), decision_id)
    if updated is None:
        console.print(f"[red]No decision with id {decision_id}.[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]Completed:[/green] {updated.title}")


@app.command()
def review(
    decision_id: Annotated[str, typer.Argument(help="Id of the decision to review.")],
    path: Annotated[
        Path,
        typer.Option("--path", "-p", help="Path to the startup workspace directory."),
    ] = Path("startup"),
) -> None:
    """Review a past decision: was it the right call, and what can we learn?"""
    decision_store = _decision_store(path)
    decision = decision_store.get(decision_id)
    if decision is None:
        console.print(f"[red]No decision with id {decision_id}.[/red]")
        raise typer.Exit(code=1)

    try:
        llm = build_llm(load_config(search_from=path).llm)
    except LLMUnavailableError as exc:
        console.print(f"[yellow]Watchtower can't reason yet:[/yellow] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"Reviewing [bold]{decision.title}[/bold]. "
        "What have you observed since? One per line, blank line to finish."
    )
    observed: list[str] = []
    while True:
        try:
            line = console.input("  - ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            break
        observed.append(line)

    result = review_decision(decision, _belief_store(path).all(), observed, llm)
    record_review(decision_store, result)
    render_review(result, decision, console)
