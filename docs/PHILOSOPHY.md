# Watchtower Engineering Philosophy

> This is the manifesto. It explains the ideas Watchtower is built on, so that the
> hundredth change to the system is as coherent as the first. When a design
> decision is hard, the answer is usually here — not in a framework's
> documentation. If you disagree with something in this document, that is an ADR,
> not a pull request.

## Watchtower is not an agent

The industry word for "LLM that does things in a loop" is *agent*. Watchtower is
deliberately **not** that. It does not plan, spawn tools, or run an open-ended
think-act loop hunting for a goal. Each turn is a **single, bounded reasoning
step** that produces a typed judgment and stops.

We reject the agent framing because agents optimize for autonomy, and autonomy is
the wrong objective for a co-founder. A co-founder's value is not that it acts on
its own; it is that it *thinks well, in the open, and changes its mind when the
evidence changes.* Everything downstream in this document follows from that
distinction.

## Watchtower is a belief-revision runtime

If Watchtower is not an agent, what is it? It is a **belief-revision runtime**: a
system whose central operation is holding a set of beliefs about the founder's
world and revising them as evidence arrives.

A belief is a *conclusion* — "memory is the next bottleneck," held with
qualitative confidence, supported and contradicted by observations. Reasoning
produces recommendations, but the durable output of a conversation is a set of
belief changes: create, strengthen, weaken, supersede, disprove. The runtime's
job is to make those changes **honest, traceable, and convergent.**

This is the lens for every feature decision. Ask: *does this help the system hold
and revise beliefs better?* If yes, it is probably kernel work. If no, it is
probably an adapter, or it does not belong at all.

## The transcript is ephemeral

Conversations are **evidence, not memory.** We do not store chat logs as the
system of record and we do not read them back to reason. A finished conversation
is compiled once, into belief changes and captured decisions, and then it is
discarded. The optional trajectory dump exists purely for human debugging and is
never fed back into reasoning.

Treating the transcript as ephemeral is a forcing function: it means the system
*must* distil, because it cannot lean on raw recall. A system that keeps every
word remembers nothing useful; a system that keeps conclusions gets sharper over
time.

## The worldview is the artifact

The product is the **worldview** — the evolving set of beliefs and the ledger of
decisions. That is what persists, what compounds in value, and what a founder
would miss if it disappeared. Chat is the interface; the worldview is the asset.

Concretely, this means the belief store and the decision ledger get the care
normally reserved for a database schema: append-only history, no silent
overwrites, superseding that links old to new, and every change logged with a
rationale. We can lose a transcript. We must never silently corrupt the worldview.

## Own everything epistemic. Rent everything mechanical.

This is the single most important rule for deciding where code goes.

- **Epistemic** work — deciding *what to believe, what to recommend, what counts
  as a decision, when to stop asking* — is Watchtower's reason to exist. We
  **own** it. It lives in the kernel, in code we control, dependency-free.
- **Mechanical** work — talking to a specific model, serializing to a specific
  file format, drawing a specific table — is undifferentiated. We **rent** it. It
  lives in adapters, behind ports, and can be replaced the day something better
  appears.

When you are unsure whether something is epistemic or mechanical, ask whether a
competitor could buy it off the shelf. If they could, rent it.

## The kernel is the intellectual property

The kernel is the company. Not the CLI, not the JSON files, not the choice of
model — those are commodities. The *way Watchtower reasons and revises beliefs* is
the differentiated thing, and it is small enough to hold in one's head precisely
because we have refused to let plumbing accumulate inside it.

So we protect it absolutely. The kernel imports no model SDK, no web or database
framework, no YAML loader, no UI toolkit — not directly and not transitively. This
is not stylistic purity for its own sake; it is how we keep the asset legible and
alive across a decade of churn in everything around it. A fitness test enforces
this on every commit, because a boundary defended only by good intentions is not
defended.

## Simplicity over cleverness

We optimize for a system that is **understandable, evolvable, and correct after
years of development** — not for code that is impressive to read once. Concretely:

- Prefer **deleting** code over adding it.
- Prefer **pure functions** and **value objects** over mutable state.
- Prefer **composition** over inheritance.
- Default to **simple, deterministic, testable, explicit, boring.**
- Do not add abstraction for a second caller that does not exist yet. Build the
  concrete thing; extract the abstraction when reality demands it, not before.

Cleverness is a loan against future understanding. We do not take that loan.

## Why framework independence matters

Frameworks are gravity. Adopt one in the core and its assumptions quietly become
your assumptions; its lifecycle becomes your lifecycle; its deprecation becomes
your rewrite. Watchtower has already outlived one such dependency — an
orchestration framework it was originally built on — and the migration away was
possible *only because the reasoning had not fused to it.*

Framework independence in the kernel buys us the right to change our minds cheaply
about everything mechanical: the model vendor, the storage engine, the transport,
the UI. That optionality is worth more than any convenience a framework offers
inside the core. We happily use frameworks at the edges, where they are rented and
replaceable.

## Why architecture changes require ADRs

The architecture described in [ARCHITECTURE.md](ARCHITECTURE.md) is assumed
correct until reality proves otherwise. That assumption is load-bearing: it is
what stops the system from being re-litigated on every pull request and slowly
eroding into mud.

So a change to the architecture — a new layer, a new port, a shift in dependency
direction, a change to what the kernel may import — is not an implementation
detail to be smuggled in with a feature. It is a decision that outlives its
author, and it must be recorded as an **Architecture Decision Record**
([ADR_TEMPLATE.md](ADR_TEMPLATE.md)): the problem, why the current design fails,
the alternatives, the tradeoffs, the migration and rollback cost, and the
decision. Writing it down forces the thinking, and it leaves a trail the next
engineer can follow to understand *why* the system is the way it is.

Ordinary features do not need an ADR. Changing the shape of the system does.

## In one paragraph

Watchtower is a belief-revision runtime, not an agent. The transcript is
ephemeral; the worldview is the artifact. We own the epistemic core and rent
everything mechanical, we keep that core small and framework-free because it is the
intellectual property, and we favour boring, deletable, testable code over clever
code. When we want to change the shape of the system, we write it down first.
