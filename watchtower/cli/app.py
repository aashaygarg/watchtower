"""Typer application defining the Watchtower CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from watchtower import __version__
from watchtower.agents.decision import PlaceholderDecisionService
from watchtower.cli.dashboard import render_morning
from watchtower.graphs.morning import MorningRoutine
from watchtower.startup.workspace import WorkspaceError
from watchtower.tools.research import GPTResearchService

app = typer.Typer(
    name="watchtower",
    help="Watchtower — a local-first AI Founder Operating System.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.command()
def version() -> None:
    """Show the Watchtower version."""
    console.print(f"[bold]watchtower[/bold] {__version__}")


@app.command()
def morning(
    path: Annotated[
        Path,
        typer.Option("--path", "-p", help="Path to the startup workspace directory."),
    ] = Path("startup"),
) -> None:
    """Run the morning routine and print the founder dashboard."""
    routine = MorningRoutine(
        research=GPTResearchService(),
        decision=PlaceholderDecisionService(),
    )
    try:
        report = routine.run(path)
    except WorkspaceError as exc:
        console.print(f"[red]Could not load startup workspace:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    render_morning(report, console)


@app.command()
def run() -> None:
    """Run the Watchtower agent loop (not implemented yet)."""
    console.print("[yellow]Not implemented yet.[/yellow]")
    raise typer.Exit(code=1)
