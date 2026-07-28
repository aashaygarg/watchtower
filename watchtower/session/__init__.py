"""Watchtower's session layer: orchestrating a conversation.

The REPL runs the read/judge/render loop; the fold compiles a finished
conversation into worldview updates and captured decisions. Both depend only on
the kernel and ports - the interface injects input and rendering, so the session
never depends on the presentation layer.
"""

from watchtower.session.fold import FoldResult, fold
from watchtower.session.repl import run

__all__ = ["FoldResult", "fold", "run"]
