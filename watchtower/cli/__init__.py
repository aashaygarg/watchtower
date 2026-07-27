"""Watchtower command-line interface."""

from __future__ import annotations

from watchtower.cli.app import app


def main() -> None:
    """Console-script entrypoint for the ``watchtower`` command."""
    app()


__all__ = ["app", "main"]
