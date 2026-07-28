"""Ephemeral conversation transcripts, for debugging only.

A *trajectory* is a versioned JSON dump of a finished conversation's turns. It is
a debugging artifact and is never read back into Watchtower: the worldview is the
product, and transcripts are discarded. Writing one has no effect on beliefs,
decisions, or any future reasoning.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

#: The on-disk schema version, so an old dump is recognizable if ever inspected.
TRAJECTORY_SCHEMA = "watchtower.trajectory/v1"


def serialize_trajectory(history: Sequence[str]) -> dict[str, object]:
    """Return the versioned, JSON-ready representation of a conversation's turns."""
    return {"schema": TRAJECTORY_SCHEMA, "turns": list(history)}


def save_trajectory(history: Sequence[str], path: Path) -> Path:
    """Write the conversation ``history`` to ``path`` as a versioned JSON transcript.

    The parent directory is created if needed. The file is a debugging artifact
    only; nothing in Watchtower ever reads it back into the worldview.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(serialize_trajectory(history), indent=2), encoding="utf-8")
    return path
