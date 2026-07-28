"""Watchtower's kernel: the reasoning core.

The kernel is the intellectual property - single-pass typed reasoning, inquiry
convergence, and (in later steps) belief revision and the decision ledger. It
imports only the domain and the ports; it never imports an adapter, an SDK, or a
framework. The oracle, stores, research, clock, and context all reach it as
ports, wired in from outside at the composition root.
"""
