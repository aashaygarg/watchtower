"""The clock port: the seam for reading the current time.

Injecting a clock keeps the kernel deterministic and testable. Production wires
a real-time clock in at the composition root; tests supply a fixed one. The
kernel reads time only through this seam.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Port for reading the current time."""

    def now(self) -> datetime:
        """Return the current moment."""
        ...
