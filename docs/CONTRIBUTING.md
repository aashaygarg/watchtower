# Contributing to Watchtower

> A practical guide to working on Watchtower without eroding it. Read
> [PHILOSOPHY.md](PHILOSOPHY.md) once for the *why* and [ARCHITECTURE.md](ARCHITECTURE.md)
> for the *what*; this document is the *how*. The golden rule: **keep the kernel
> pure and dependencies pointing inward.**

## The five questions

Before writing any feature, answer these. They are not ceremony; they route the
work to the right place.

1. **Does this belong in the kernel?** Only if it is *epistemic* — it decides what
   to believe, what to recommend, what counts as a decision, or when to stop
   asking.
2. **Is this merely an adapter?** If it talks to a model, a disk, a network, or a
   screen, it is mechanical — it belongs behind a port.
3. **Is there already a suitable abstraction?** Prefer extending an existing port
   or kernel function over inventing a new one.
4. **Can this be implemented with less code?** The smallest correct version wins.
5. **Will this still make sense in two years?** If it depends on a vendor's
   current API shape or a framework's current fashion, keep it at the edge.

## The validation gate

Run this after **every** change. A change is not done until it passes:

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

Do not commit with a red gate. (As a matter of workflow, leave changes in the
working tree for review; the author commits.)

## Adding a new feature

1. Run the five questions to place the work.
2. If it is epistemic, add or extend a **pure function** in the kernel that takes
   domain values and ports and returns domain values. No new I/O.
3. If it needs an external capability, define or reuse a **port**, and put the
   concrete work in an **adapter**.
4. Wire any new concrete adapter in `bootstrap.py` — nowhere else.
5. Add tests (see *Testing expectations*). Keep behaviour changes covered on both
   the happy path and the failure/opt-out path.
6. If the change alters the *shape* of the system, stop and write an ADR first.

## Adding an adapter

An adapter is the concrete implementation of an existing port.

- Put it under the matching `adapters/` subpackage (`providers/`, `persistence/`,
  `research/`).
- Implement the port's methods; depend only on `domain`, `ports`, and the
  vendor/library you are wrapping.
- Do **not** import another ring inward of `adapters` beyond `domain`/`ports`, and
  never import `bootstrap`.
- Construct it in `bootstrap.py`. The kernel, session, and interface must not name
  your class.
- Degrade honestly on failure rather than crashing the caller (see the provider
  retry/`degraded_payload` pattern for the reference approach).

## Adding a provider

Providers are LLM adapters implementing the `Oracle` port (`complete`,
`complete_json`).

1. Add `adapters/providers/<name>.py` with a class that satisfies `Oracle`.
2. Import the vendor SDK **lazily inside `__init__`**, raising
   `LLMUnavailableError` if the package is missing — the SDK is an optional extra,
   not a hard dependency.
3. Wrap `complete_json` in `call_with_retry(..., default_factory=degraded_payload)`
   so a transient failure degrades instead of crashing the REPL.
4. Register the provider in `adapters/providers/factory.py` (`build_oracle`), and
   add its key-environment default.
5. Add tests for construction, the happy path via a fake, and the degraded path.

## Adding a port

A port is a new seam — reach for it only when there is (or is imminently) a real
second implementation or a genuine need to invert a dependency. A port with one
implementation and no prospect of another is a speculative abstraction; do not add
it.

1. Add `ports/<name>.py` defining a `Protocol` phrased in **domain terms only**.
2. It may import `domain` and nothing else at runtime. If a signature needs an
   adapter type for annotation, use a `TYPE_CHECKING` import so there is no runtime
   coupling.
3. Add at least one adapter that implements it and wire it in `bootstrap.py`.
4. If introducing the port changes the architecture (a new kind of dependency
   inversion, a new ring interaction), it needs an ADR.

## When code belongs in the kernel

Put it in the kernel **only** if all of these hold:

- It is epistemic (belief/decision/inquiry/recommendation logic).
- It can be written as pure functions over `domain` values and `ports`.
- It imports nothing but `domain` and `ports`.
- It does not read files, call the network, touch a model SDK, or render output.

If any of those fail, it is adapter, session, or interface work.

## Testing expectations

- **Cover the diff.** Every new or changed line — including the failure, opt-out,
  and fallback branches — should be exercised by an assertion-backed test.
- **Kernel tests use fakes.** Satisfy a port in a few lines; never mock an SDK.
- **Test behaviour, not internals**, except where an invariant (e.g. "beliefs
  change in exactly one place") is worth pinning explicitly.
- **Prompts are behaviour.** If you touch the system prompt, prove intent — an
  unintended change to `_DIALOGUE_SYSTEM` is a defect.
- **Persistence and revision semantics are behaviour.** Changes to append-only
  logging, superseding, capture rules, or the destructive-change guard must be
  covered on both the changed and unchanged paths.

## Architecture fitness tests

`tests/test_architecture.py` is the constitution, executable. It fails the build
if:

- the kernel imports an adapter, a provider SDK, a framework, a YAML loader, or
  `bootstrap` — statically **or transitively** (checked by importing the kernel in
  a fresh interpreter);
- a port imports anything but `domain`;
- an inner ring imports the composition root.

**Never weaken these tests to make a change pass.** A red fitness test means the
change is reaching outward — fix the design, not the test. These are a required CI
check.

## Review checklist

Before requesting review, confirm:

- [ ] Dependencies point inward; nothing new imports outward.
- [ ] The kernel imports only `domain` and `ports`.
- [ ] New adapters are constructed only in `bootstrap.py`.
- [ ] No new speculative abstraction, layer, or dependency.
- [ ] The diff is minimal and every changed line is tested.
- [ ] No prompt / persistence / revision / capture semantics changed
      unintentionally.
- [ ] `ruff check`, `ruff format --check`, and `pytest` are green.
- [ ] Any change to the *shape* of the system has an accompanying ADR.

## Common mistakes

- Importing a provider class or a JSON store outside `bootstrap.py`.
- Letting an SDK or framework type leak into a kernel or port signature at
  runtime (use `TYPE_CHECKING` for annotation-only references).
- Fusing a pure value type into a module that also does I/O (this once made the
  kernel import a YAML loader transitively — keep value objects in pure modules).
- Adding a port or a config flag for a caller that does not exist yet.
- "Improving" adjacent code while fixing a bug — keep changes surgical.
- Reaching for embeddings, vector stores, or a retrieval framework where lexical
  overlap already does the job.

## Anti-patterns

- **The kernel as a hub.** The kernel calling out to a concrete adapter, service
  locator, or global. The kernel receives ports; it does not fetch them.
- **The transcript as memory.** Reading chat logs back to reason. The worldview is
  the memory; the transcript is discarded.
- **Inferred decisions.** Capturing a decision from Watchtower's recommendation. A
  decision requires an explicit founder commitment.
- **Silent overwrites.** Mutating a belief or decision in place without logging or
  superseding. History is append-only.
- **Framework in the core.** Any orchestration/agent/vector framework inside
  `kernel/`. Frameworks are rented at the edges.
- **Speculative seams.** New ports/abstractions "for flexibility" with no real
  second implementation.

## Future evolution

Deferred work is summarized in
[ARCHITECTURE.md](ARCHITECTURE.md#15-future-evolution-deferred-not-prescribed).
Do not begin any of it without an approved ADR. In particular, the reserved
`ContextProvider` port and the typed `Observation`/`Evidence` model are
intentionally unbuilt.
