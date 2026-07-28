"""The research port: the seam for gathering external context.

Watchtower's kernel never reaches the outside world directly. A
:class:`ResearchProvider` turns the current workspace into a research briefing;
concrete providers - live or placeholder - live outside the kernel and are wired
in at the composition root. Research therefore only ever enters Watchtower as
grounded findings, never as a hidden reasoning loop.

The briefing type lives in :mod:`watchtower.adapters.research` and is referenced
here only for type checking, so this port has no runtime dependency on any
adapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from watchtower.adapters.research import ResearchBriefing
    from watchtower.startup.models import StartupWorkspace


class ResearchProvider(Protocol):
    """Port for producing a research briefing from a workspace."""

    def investigate(self, workspace: StartupWorkspace) -> ResearchBriefing:
        """Return a research briefing for the given ``workspace``."""
        ...
