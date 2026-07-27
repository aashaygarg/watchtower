"""Watchtower's domain layer: pure, immutable, serializable data.

The domain is the innermost ring of the architecture. It holds the vocabulary
the rest of Watchtower reasons about - beliefs, decisions, inquiries, judgments,
and messages - as frozen dataclasses and enums. It depends on nothing but the
standard library: no LLM, no storage, no ports, no framework. Everything else
imports the domain; the domain imports nothing back.
"""
