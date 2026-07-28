"""Watchtower's adapters: concrete implementations of the ports.

Adapters are the outer ring - provider SDKs, storage engines, research, context.
Each implements a port from :mod:`watchtower.ports`; nothing in the kernel or the
domain imports them. They are wired to the ports at the composition root, the one
place that knows both sides.
"""
