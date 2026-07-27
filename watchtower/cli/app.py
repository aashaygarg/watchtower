"""Typer application defining the Watchtower CLI."""

from __future__ import annotations

import typer
from rich.console import Console

from watchtower import __version__

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
def run() -> None:
    """Run the Watchtower agent loop (not implemented yet)."""
    console.print("[yellow]Not implemented yet.[/yellow]")
    raise typer.Exit(code=1)
