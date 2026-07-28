# ADR NNNN — <short title>

> Copy this file to `docs/adr/NNNN-<kebab-title>.md` (zero-padded, incrementing)
> for any change to the **shape** of the system: a new layer or ring, a new port,
> a change in dependency direction, a change to what the kernel may import, or a
> new external dependency. Ordinary features do not need an ADR. Keep it short —
> an ADR that is too long to read will not be read.

- **Status:** Proposed | Accepted | Rejected | Superseded by ADR-NNNN
- **Date:** YYYY-MM-DD
- **Deciders:** <names>

## Context

What is the situation that makes this decision necessary? State the forces at play
in a few sentences — the goal, the constraint, the pressure. Assume the reader
knows the architecture but not this problem.

## Problem

The specific thing that needs deciding, stated as a question or a sharp
one-paragraph description. If there is no real problem, there is no ADR.

## Current architecture

How the system handles this today, and precisely **why that is insufficient** for
the case at hand. Cite the concrete module or boundary. If the current design is
not actually failing, stop here — the default is to keep it.

## Proposed change

The change, described concretely: which ring, which module, which port, which
dependency edge. State explicitly what the kernel would or would not import after
this change.

## Alternatives considered

At least two, including "do nothing." For each: a one-line description and why it
was not chosen. An ADR with no alternatives has not been thought through.

- **Do nothing.** …
- **Alternative A.** …
- **Alternative B.** …

## Tradeoffs

What we gain and what we give up. Be honest about the cost, especially any cost to
kernel purity, inward dependency flow, testability, or simplicity. If the change
adds a layer, a dependency, or a speculative seam, justify it here.

## Migration strategy

How we get from here to there without a red build: the ordered, independently
shippable steps, and how existing behaviour is preserved at each one. Note which
fitness tests or contracts protect the transition.

## Rollback strategy

How we undo this if it proves wrong — the concrete revert path and any data or
schema implications. If rollback is hard, say so; that is itself a tradeoff.

## Decision

The chosen option, in one or two sentences. Unambiguous.

## Consequences

What becomes true after this lands — positive and negative, immediate and
long-term. Include new invariants to uphold, new fitness checks to add, and any
follow-up work this enables or requires.
