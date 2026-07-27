"""A minimal registry for agent-callable tools."""

from __future__ import annotations

from collections.abc import Callable

_REGISTRY: dict[str, Callable[..., object]] = {}


def register(name: str) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Return a decorator that registers a callable tool under ``name``."""

    def decorator(func: Callable[..., object]) -> Callable[..., object]:
        _REGISTRY[name] = func
        return func

    return decorator


def get(name: str) -> Callable[..., object]:
    """Return the tool registered under ``name``."""
    return _REGISTRY[name]


def available() -> list[str]:
    """Return the sorted names of all registered tools."""
    return sorted(_REGISTRY)
