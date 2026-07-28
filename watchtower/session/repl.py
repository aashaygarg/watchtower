"""The reasoning REPL: read a message, judge it, render the turn, repeat.

The loop is orchestration, not presentation. It takes the ports it reasons with
and callbacks for reading input and rendering a turn, so it never depends on the
interface layer.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from watchtower.adapters.persistence.trajectory import save_trajectory
from watchtower.domain.beliefs import Belief
from watchtower.domain.judgment import ThinkingResult
from watchtower.kernel.reasoning import think
from watchtower.kernel.worldview import format_for_prompt, select_relevant
from watchtower.ports.oracle import Oracle
from watchtower.startup.models import StartupWorkspace


def run(
    *,
    workspace: StartupWorkspace,
    oracle: Oracle,
    beliefs: Sequence[Belief],
    read_input: Callable[[], str],
    render_turn: Callable[[ThinkingResult], None],
    trajectory_path: Path | None = None,
) -> list[str]:
    """Run the interactive reasoning loop and return the conversation history.

    ``read_input`` yields the founder's next message; ``render_turn`` presents a
    completed turn. The loop ends on an empty line, ``exit``/``quit``, or EOF.

    When ``trajectory_path`` is given, the finished transcript is written there as
    an ephemeral debugging artifact; it is never read back into the worldview.
    """
    history: list[str] = []
    inquiries = ()
    while True:
        try:
            message = read_input()
        except (EOFError, KeyboardInterrupt):
            break
        if message.lower() in {"exit", "quit", ""}:
            break
        relevant = format_for_prompt(select_relevant(beliefs, message))
        result = think(
            message,
            workspace=workspace,
            llm=oracle,
            history=history,
            beliefs=relevant,
            inquiries=inquiries,
        )
        render_turn(result)
        inquiries = result.inquiries
        history.append(f"You: {message}")
        spoken = result.recommendation or result.current_thinking or result.understanding or ""
        if result.question:
            spoken = f"{spoken} (asked: {result.question})".strip()
        history.append(f"Watchtower: {spoken}")
    if trajectory_path is not None:
        save_trajectory(history, trajectory_path)
    return history
