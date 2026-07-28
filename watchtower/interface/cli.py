"""Typer application defining the Watchtower CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from watchtower import __version__
from watchtower.bootstrap import LLMUnavailableError, build_context, build_oracle_for
from watchtower.interface.beliefs_view import render_belief_updates, render_beliefs
from watchtower.interface.decisions_view import render_captured, render_review, render_timeline
from watchtower.interface.render import render_thinking
from watchtower.kernel.ledger import mark_completed, record_review, review_decision
from watchtower.ports.stores import BeliefStore, DecisionStore
from watchtower.session import fold, run
from watchtower.startup.workspace import WorkspaceError, load_workspace

app = typer.Typer(
    name="watchtower",
    help="Watchtower — a local-first AI Founder Operating System.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _belief_store(path: Path) -> BeliefStore:
    return build_context(path).belief_store


def _decision_store(path: Path) -> DecisionStore:
    return build_context(path).decision_store


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
        llm = build_oracle_for(path)
    except LLMUnavailableError as exc:
        console.print(f"[yellow]Watchtower can't reason yet:[/yellow] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"[bold]Watchtower[/bold] is ready to think about [bold]{workspace.startup.name}[/bold]. "
        "Describe a problem, or type 'exit' to leave."
    )

    store = _belief_store(path)
    history = run(
        workspace=workspace,
        oracle=llm,
        beliefs=store.all(),
        read_input=lambda: console.input("\n[bold cyan]you[/bold cyan] > ").strip(),
        render_turn=lambda result: render_thinking(result, console),
    )

    # Every conversation becomes evidence: update the worldview, never the transcript.
    if history:
        outcome = fold(
            history=history,
            belief_store=store,
            decision_store=_decision_store(path),
            oracle=llm,
        )
        render_belief_updates(outcome.belief_updates, console)
        if outcome.captured_decisions:
            render_captured(outcome.captured_decisions, console)

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
        llm = build_oracle_for(path)
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


def main() -> None:
    """Console-script entrypoint for the ``watchtower`` command."""
    app()
