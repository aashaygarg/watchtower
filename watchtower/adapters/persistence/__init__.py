"""Persistence adapters: local JSON-backed belief and decision stores.

These implement the :class:`~watchtower.ports.stores.BeliefStore` and
:class:`~watchtower.ports.stores.DecisionStore` protocols against the local
filesystem. A future SQLite or Postgres adapter would live here too, swapped in
at the composition root without touching the kernel.
"""

from watchtower.adapters.persistence.json_beliefs import JsonBeliefStore
from watchtower.adapters.persistence.json_decisions import JsonDecisionStore

__all__ = [
    "JsonBeliefStore",
    "JsonDecisionStore",
]
