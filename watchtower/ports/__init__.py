"""Watchtower's ports: the interfaces the kernel depends on.

Ports are protocols - the seams between the reasoning kernel and the outside
world. The kernel imports the domain and these ports, nothing else; concrete
adapters implement the protocols and are wired in at the composition root. This
keeps providers, storage, research, and time replaceable without touching the
kernel.
"""
