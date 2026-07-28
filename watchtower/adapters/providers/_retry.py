"""Bounded retry for oracle calls.

A provider call is wrapped in a small, generic retry loop: it is attempted up to
``attempts`` times, and if every attempt fails the caller-supplied
``default_factory`` produces a typed fallback value instead of the error
propagating. This keeps a transient provider failure from crashing the reasoning
loop while never hiding a permanent failure behind an untyped ``None``.
"""

from __future__ import annotations

from collections.abc import Callable

#: The default number of attempts a provider makes before returning its fallback.
DEFAULT_ATTEMPTS = 3


def call_with_retry[T](
    fn: Callable[[], T],
    *,
    attempts: int,
    default_factory: Callable[[], T],
) -> T:
    """Call ``fn`` up to ``attempts`` times; return ``default_factory()`` on total failure.

    Each attempt runs ``fn`` with no arguments and the first success is returned
    immediately. If every attempt raises, the final exception is swallowed and a
    typed default is produced instead - the caller always receives a value of
    type ``T``.

    Args:
        fn: The zero-argument operation to attempt (for example a provider call).
        attempts: The maximum number of attempts; must be at least 1.
        default_factory: Produces the fallback value when all attempts fail.

    Returns:
        The result of the first successful call, or ``default_factory()`` if none succeed.

    Raises:
        ValueError: If ``attempts`` is less than 1.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    last = attempts - 1
    for attempt in range(attempts):
        try:
            return fn()
        except Exception:
            if attempt == last:
                return default_factory()
    return default_factory()  # unreachable: the loop always returns on its last attempt
