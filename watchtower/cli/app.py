"""Typer application defining the Watchtower CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from watchtower import __version__
from watchtower.agents.decision import PlaceholderDecisionService
from watchtower.cli.conversation import render_thinking
from watchtower.cli.dashboard import render_morning
from watchtower.cognition import think
from watchtower.config import load_config
from watchtower.graphs.morning import MorningRoutine
from watchtower.llm import LLMUnavailableError, build_llm
from watchtower.startup.workspace import WorkspaceError, load_workspace
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

    research = GPTResearchService()
    console.print(
        f"[bold]Watchtower[/bold] is ready to think about [bold]{workspace.startup.name}[/bold]. "
        "Describe a problem, or type 'exit' to leave."
    )

    history: list[str] = []
    while True:
        try:
            message = console.input("\n[bold cyan]you[/bold cyan] > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if message.lower() in {"exit", "quit", ""}:
            break
        result = think(message, workspace=workspace, llm=llm, research=research, history=history)
        render_thinking(result, console)
        history.append(f"You: {message}")
        history.append(f"Watchtower: {result.recommendation}")

    console.print("\n[dim]Ended.[/dim]")


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
